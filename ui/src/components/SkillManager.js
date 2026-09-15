import { jsxs as _jsxs, jsx as _jsx, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
export function SkillManager() {
    const navigate = useNavigate();
    const [skills, setSkills] = useState([]);
    const [newSkill, setNewSkill] = useState({
        id: "",
        name: "",
        description: "",
        category: "automation",
        status: "pending",
    });
    const [isLoading, setIsLoading] = useState(false);
    // Load skills from API or registry
    useEffect(() => {
        // Load registered skills from the Jefrey skill registry
        // This would connect to the skill system
        const mockSkills = [
            {
                id: "notes",
                name: "Notes",
                description: "CRUD de notas com busca semântica",
                category: "knowledge",
                status: "active",
            },
            {
                id: "automation",
                name: "Automação",
                description: "Workflow automation with user_id isolation",
                category: "automation",
                status: "active",
            },
            {
                id: "web_search",
                name: "Web Search",
                description: "Busca web via Tavily/DDG",
                category: "integration",
                status: "active",
            },
        ];
        setSkills(mockSkills);
    }, [navigate]);
    const handleAddSkill = async () => {
        if (!newSkill.name.trim())
            return;
        setIsLoading(true);
        try {
            // Here we would register the new skill with the Jefrey skill system
            // For now, add to local state and navigate to setup
            const newSkillWithId = {
                ...newSkill,
                id: newSkill.name.toLowerCase().replace(/[^a-z0-9]/g, "_") || crypto.randomUUID(),
                lastExecution: new Date().toISOString(),
            };
            setSkills((prev) => [...prev, newSkillWithId]);
            setNewSkill({ id: "", name: "", description: "", category: "automation", status: "pending" });
            // Navigate to skill configuration
            navigate(`/skills/${newSkillWithId.id}/configure`);
        }
        catch (e) {
            console.error("Failed to add skill:", e);
        }
        finally {
            setIsLoading(false);
        }
    };
    const handleEditSkill = (id) => {
        navigate(`/skills/${id}/configure`);
    };
    return (_jsxs(Card, { className: "glass-strong border-indigo-500/10", children: [_jsx(CardHeader, { children: _jsxs(CardTitle, { className: "flex items-center gap-2", children: [_jsxs(Badge, { variant: "secondary", className: "text-xs", children: [skills.length, " Skills"] }), "Gerenciar Skills"] }) }), _jsxs(CardContent, { children: [isLoading && (_jsx("p", { className: "text-sm text-muted-foreground", children: "Carregando skills..." })), skills.length === 0 && (_jsx("p", { className: "text-sm text-muted-foreground", children: "Nenhuma skill cadastrada. Clique abaixo para adicionar sua primeira skill." })), _jsx("div", { className: "space-y-3 pt-3 border-t border-indigo-500/10", children: skills.map((skill) => (_jsxs("div", { className: "flex items-center gap-3 p-2 rounded-md bg-card/50 transition-colors", children: [_jsx(Badge, { variant: skill.status === "active" ? "default" : skill.status === "error" ? "destructive" : "outline", className: "text-xs", children: skill.status }), _jsx("span", { className: "font-medium truncate", children: skill.name }), _jsx("span", { className: "text-xs text-muted-foreground", children: skill.description }), _jsxs("div", { className: "ml-auto flex gap-1", children: [_jsx(Button, { variant: "ghost", size: "icon", onClick: () => handleEditSkill(skill.id), "aria-label": "Configurar skill", children: _jsxs("svg", { className: "h-4 w-4", fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", children: [_jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M11 3.979a1 1 0 011.414 1.414l7 7a1 1 0 010 1.414l-7 7a1 1 0 01-1.414-1.414L15 7.079V3.979a1 1 0 011.414-1.414z" }), _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M18.364 5.636l-1.414-1.415-7 7a1 1 0 01-1.414 0l-7-7a1 1 0 011.414-1.414L12 9.906l6.364-6.364a1 1 0 011.414 0z" })] }) }), _jsx(Button, { variant: "ghost", size: "icon", onClick: () => {
                                                // Remove skill - in production would have confirmation
                                                setSkills((prev) => prev.filter((s) => s.id !== skill.id));
                                            }, "aria-label": "Remover skill", children: _jsxs("svg", { className: "h-4 w-4", fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", children: [_jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M19 7l-.867 12.832A2 2 0 0116.168 21H7.832a2 2 0 01-1.995-1.832L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3m4 6h.01M4.234 5.234a1 1 0 010 1.414l1.414 1.414a1 1 0 01-1.414 1.414l-1.414-1.414a1 1 0 011.414-1.414l1.414 1.414a1 1 0 011.414 1.414l-1.414 1.414a1 1 0 01-1.414-1.414L4.234 5.234z" }), _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M14 7v5a2 2 0 002 2h4a2 2 0 002-2v-5m-7-3h7m-7 0h7m-7-7h7" })] }) })] })] }, skill.id))) })] })] })) /* Add New Skill Form */;
    { /* Add New Skill Form */ }
    _jsxs(Card, { className: "mt-4 glass-strong border-indigo-500/10", children: [_jsx(CardHeader, { children: _jsxs(CardTitle, { className: "flex items-center gap-2", children: [_jsx(Plus, { className: "h-4 w-4 text-indigo-400" }), "Adicionar Nova Skill", _jsx(Badge, { variant: "outline", className: "text-xs ml-2", children: "+99 mais" })] }) }), _jsxs(CardContent, { children: [_jsx("p", { className: "text-sm text-muted-foreground mb-3", children: "Adicione novas capacidades ao Jefrey. O sistema suporta automa\u00E7\u00F5es, integra\u00E7\u00F5es, mem\u00F3ria e interface personalizada." }), _jsxs("form", { onSubmit: (e) => {
                            e.preventDefault();
                            handleAddSkill();
                        }, className: "space-y-3", children: [_jsxs("div", { className: "grid grid-cols-2 gap-3", children: [_jsxs("div", { className: "space-y-1", children: [_jsx("label", { className: "text-xs text-muted-foreground uppercase", children: "Nome da Skill" }), _jsx(Input, { value: newSkill.name, onChange: (e) => setNewSkill({
                                                    ...newSkill,
                                                    name: e.target.value,
                                                }), placeholder: "Ex: QR Remote, Morning Briefing, HW Monitor", required: true, disabled: isLoading })] }), _jsxs("div", { className: "space-y-1", children: [_jsx("label", { className: "text-xs text-muted-foreground uppercase", children: "Categoria" }), _jsxs(Select, { value: newSkill.category, onValueChange: (v) => setNewSkill({ ...newSkill, category: v }), children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "automation", children: "Automa\u00E7\u00E3o" }), _jsx(SelectItem, { value: "integration", children: "Integra\u00E7\u00E3o" }), _jsx(SelectItem, { value: "memory", children: "Mem\u00F3ria" }), _jsx(SelectItem, { value: "knowledge", children: "Conhecimento" }), _jsx(SelectItem, { value: "ui", children: "Interface" })] })] })] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-3", children: [_jsxs("div", { className: "space-y-1", children: [_jsx("label", { className: "text-xs text-muted-foreground uppercase", children: "Descri\u00E7\u00E3o" }), _jsx(Input, { value: newSkill.description, onChange: (e) => setNewSkill({
                                                    ...newSkill,
                                                    description: e.target.value,
                                                }), placeholder: "Descreva o que esta skill faz", rows: 2, disabled: isLoading })] }), _jsxs("div", { className: "space-y-1", children: [_jsx("label", { className: "text-xs text-muted-foreground uppercase", children: "Status" }), _jsxs(Select, { value: newSkill.status, onValueChange: (v) => setNewSkill({ ...newSkill, status: v }), children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, {}) }), _jsxs(SelectContent, { children: [_jsx(SelectItem, { value: "pending", children: "Pending" }), _jsx(SelectItem, { value: "active", children: "Active" }), _jsx(SelectItem, { value: "error", children: "Error" })] })] })] })] }), _jsx(Button, { type: "submit", disabled: isLoading || !newSkill.name.trim(), className: "w-full", children: isLoading ? (_jsxs(_Fragment, { children: [_jsx("span", { className: "inline-block h-4 w-4 animate-spin rounded-full border-b-2 border-current" }), " Adicionando..."] })) : "Adicionar Skill ao Jefrey" })] })] })] });
}
