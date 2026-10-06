/** Pergunta antes de uma acao com efeito real (risco alto). So a pessoa decide. */
export default function ApprovalDialog({ label, onDecide }: { label?: string; onDecide: (d: "approved" | "rejected") => void }) {
  return (
    <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/55 p-4" role="alertdialog" aria-label="Aprovação necessária">
      <div className="jf-panel w-full max-w-md border-amber-400/40 bg-[#07141b] p-5">
        <p className="text-lg font-medium text-amber-200">Preciso da sua aprovação</p>
        <p className="mt-1 text-base text-white/75">
          {label ? <>Ação: <b>{label}</b>. </> : null}Pode ter efeitos reais. Você autoriza?
        </p>
        <div className="mt-4 flex gap-2">
          <button type="button" onClick={() => onDecide("approved")} className="jf-btn jf-focus px-5 py-2.5 text-base">Aprovar</button>
          <button type="button" onClick={() => onDecide("rejected")} className="jf-focus rounded-lg border border-white/20 px-5 py-2.5 text-base text-white/85 hover:bg-white/5">Negar</button>
        </div>
      </div>
    </div>
  )
}
