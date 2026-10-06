import AvatarPicker from "@/components/AvatarPicker"
import type { useSpeaker } from "@/hooks/useSpeaker"

type Speaker = ReturnType<typeof useSpeaker>

/** Menu do botao de engrenagem: avatar, voz, conversa continua, chamar pelo nome e painel Jarvis. */
export default function OptionsMenu(p: {
  speaker: Speaker
  listenerSupported: boolean
  voiceReply: boolean
  onVoiceReply: (on: boolean) => void
  continuous: boolean
  onContinuous: (on: boolean) => void
  wakeOn: boolean
  onToggleWake: () => void
  hud: boolean
  onHud: (on: boolean) => void
}) {
  const { speaker } = p
  return (
    <div className="jf-glass absolute bottom-11 left-0 z-40 w-64 space-y-2 rounded-xl p-3 text-sm text-white/80">
      <AvatarPicker />
      {speaker.supported && (
        <label className="flex cursor-pointer items-center gap-2">
          <input type="checkbox" checked={p.voiceReply} onChange={e => { p.onVoiceReply(e.target.checked); if (!e.target.checked) speaker.cancel() }} />
          Falar as respostas
        </label>
      )}
      {speaker.supported && (speaker.voices.length > 1 || speaker.cloudOk) && (
        <label className="block text-xs text-white/60">
          Voz
          <select
            value={speaker.voiceChoice ?? ""}
            onChange={e => { speaker.setVoice(e.target.value || null); speaker.cancel(); speaker.say("Oi, essa é a minha voz.") }}
            className="jf-focus mt-1 w-full rounded-lg border border-white/20 bg-black/60 px-2 py-1.5 text-sm text-white"
          >
            <option value="">Automática (a mais natural)</option>
            {speaker.engines?.engines.filter(e => e.id !== "browser" && e.available).map(e => <option key={e.id} value={e.id}>{e.label}</option>)}
            {speaker.voices.map(v => <option key={v.uri} value={v.uri}>{v.name.replace(/^Microsoft /, "")}</option>)}
          </select>
        </label>
      )}
      {p.listenerSupported && (
        <label className="flex cursor-pointer items-center gap-2">
          <input type="checkbox" checked={p.continuous} onChange={e => p.onContinuous(e.target.checked)} />
          Conversa contínua
        </label>
      )}
      {p.listenerSupported && (
        <label className="flex cursor-pointer items-center gap-2" title="O microfone fica ligado e eu só entendo o que você fala quando começa com 'Jefrey'. Nada é guardado nem enviado para a internet.">
          <input type="checkbox" checked={p.wakeOn} onChange={p.onToggleWake} />
          Chamar pelo nome ("Jefrey, …")
        </label>
      )}
      <label className="flex cursor-pointer items-center gap-2" title="Medidores e registro sobre o avatar (telas largas)">
        <input type="checkbox" checked={p.hud} onChange={e => p.onHud(e.target.checked)} />
        Painel Jarvis
      </label>
    </div>
  )
}
