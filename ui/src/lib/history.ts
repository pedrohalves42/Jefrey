// Upload/Generation History - localStorage wrapper
export interface UploadHistoryItem {
  id: string
  name: string
  size: number
  type: string
  uploadedAt: string
  url?: string
}

export interface GenerationHistoryItem {
  id: string
  type: "chat" | "memory" | "automation"
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
}

const UPLOAD_HISTORY_KEY = "jefrey_upload_history"
const GENERATION_HISTORY_KEY = "jefrey_generation_history"

export function getUploadHistory(): UploadHistoryItem[] {
  try {
    const data = localStorage.getItem(UPLOAD_HISTORY_KEY)
    return data ? JSON.parse(data) : []
  } catch {
    return []
  }
}

export function addUploadHistory(item: Omit<UploadHistoryItem, "id" | "uploadedAt">): void {
  try {
    const history = getUploadHistory()
    const newItem: UploadHistoryItem = {
      ...item,
      id: crypto.randomUUID(),
      uploadedAt: new Date().toISOString(),
    }
    history.unshift(newItem)
    localStorage.setItem(UPLOAD_HISTORY_KEY, JSON.stringify(history))
  } catch (e) {
    console.error("Failed to add upload history:", e)
  }
}

export function clearUploadHistory(): void {
  try {
    localStorage.removeItem(UPLOAD_HISTORY_KEY)
  } catch (e) {
    console.error("Failed to clear upload history:", e)
  }
}

export function getGenerationHistory(): GenerationHistoryItem[] {
  try {
    const data = localStorage.getItem(GENERATION_HISTORY_KEY)
    return data ? JSON.parse(data) : []
  } catch {
    return []
  }
}

export function addGenerationHistory(item: Omit<GenerationHistoryItem, "id" | "timestamp">): void {
  try {
    const history = getGenerationHistory()
    const newItem: GenerationHistoryItem = {
      ...item,
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    }
    history.unshift(newItem)
    // Manter apenas últimos 100 itens
    if (history.length > 100) {
      history.pop()
    }
    localStorage.setItem(GENERATION_HISTORY_KEY, JSON.stringify(history))
  } catch (e) {
    console.error("Failed to add generation history:", e)
  }
}

export function clearGenerationHistory(): void {
  try {
    localStorage.removeItem(GENERATION_HISTORY_KEY)
  } catch (e) {
    console.error("Failed to clear generation history:", e)
  }
}
