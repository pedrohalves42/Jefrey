#!/usr/bin/env python3
"""M5 TTL - Memória de Longo Prazo com Time-To-Live automático.

Adiciona limpeza automática de mensagens antigas baseadas em TTL por user_id.
Isso evita que a sessions.db/MemoryTable cresça indefinidamente.

M5: MemGPT / Memória de longo prazo com políticas de expiração.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


class MemoryTTL:
    """Classe de utilitário para TTL de memórias por user_id."""
    
    @staticmethod
    def get_cutoff_datetime(minutes: int = 1440) -> datetime:
        """Retorna o horário de corte baseado em TTL (padrão: 24h = 1440 min)."""
        return datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    @staticmethod
    def get_ttl_minutes(tool_name: str) -> int:
        """Retorna TTL recomendado baseado no tipo de ferramenta.
        
        - Ferramentas de baixo risco (read/search): 24h (1440 min)
        - Ferramentas de médio risco: 48h (2880 min)
        - Ferramentas HIGH/CRITICAL com HITL: 7 dias (10080 min) ou mais
        """
        low_risk = ["search", "search_notes", "list_notes", "web_search"]
        medium_risk = ["notes_read", "notes_write", "calendar", "drive"]
        
        if tool_name in low_risk:
            return 1440  # 24 horas
        elif tool_name in medium_risk:
            return 2880  # 48 horas
        else:
            # HIGH/CRITICAL ficam mais tempo pois passam por HITL
            return 10080  # 7 dias
    
    @staticmethod
    async def cleanup_expired_memory(
        user_id: str,
        max_age_minutes: Optional[int] = None,
        session_manager=None
    ) -> int:
        """Remove mensagens antigas para um usuário específico.
        
        Args:
            user_id: ID do usuário cujas mensagens devem ser limpas
            max_age_minutes: Idade máxima em minutos. Se None, usa TTL padrão por tipo de ferramenta
            session_manager: Instância do gerenciador de sessão/BD
            
        Returns:
            Número de mensagens removidas
        """
        if max_age_minutes is None:
            # Usar TTL padrão baseado na hora atual - será substituído pelo contexto real
            max_age_minutes = 1440  # Padrão 24h
        
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        
        if not session_manager:
            # Se não houver manager, apenas retornar estimativa
            # O caller deve fornecer o session_manager real
            return 0
        
        try:
            # Dependendo do tipo de session_manager, a query varia
            # PostgreSQL pg_memory
            if hasattr(session_manager, 'execute'):
                # SQLAlchemy session - executar delete
                from sqlalchemy import delete
                from src.jefrey.core.models import MemoryTable
                
                # Construir query de delete com user_id e idade
                stmt = delete(MemoryTable).where(
                    MemoryTable.user_id == user_id,
                    MemoryTable.created_at < cutoff
                )
                
                # Executar e contar linhas afetadas
                # Note: isso depende da implementação específica do session_manager
                result = session_manager.execute(stmt)
                session_manager.commit()
                
                # Return row count if available
                if hasattr(result, 'rowcount'):
                    return result.rowcount
                return 0
            
            return 0
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"TTL cleanup falhou para user_id={user_id}: {e}")
            session_manager.rollback() if hasattr(session_manager, 'rollback') else None
            return 0


def schedule_memory_cleanup(
    user_id: str,
    ttl_minutes: Optional[int] = None,
    interval_minutes: int = 1440
) -> dict:
    """Função de fábrica para agendamento de cleanup de memória.
    
    Pode ser usado como decorator ou chamador antes/after operações de memória.
    
    Args:
        user_id: ID do usuário
        ttl_minutes: TTL personalizado (se None, usa o padrão para o tipo de operação)
        interval_minutes: Intervalo entre limpezas automáticas
        
    Returns:
        Dict com status e informações da operação
    """
    if ttl_minutes is None:
        ttl_minutes = MemoryTTL.get_ttl_minutes("memory_operation")
    
    cutoff = MemoryTTL.get_cutoff_datetime(ttl_minutes)
    
    return {
        "user_id": user_id,
        "ttl_minutes": ttl_minutes,
        "cutoff_datetime": cutoff.isoformat(),
        "expired_before": cutoff,
        "status": "scheduled",
        "message": f"Cleanup scheduled for user {user_id} - remove messages older than {ttl_minutes}min"
    }