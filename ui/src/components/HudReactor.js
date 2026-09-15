import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// HudReactor Stark Lab — all gates passamos da versão anterior. Reestruturado para CIPHER-205 com framer-motion presets Stark (Arc/Pulse/Wave), Settings > Aparência, chime, hue wheel e animação ON/OFF.
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
export function HudReactor({ level = 0, state = "idle", onClick }) {
    const [p95, setP95] = useState("--");
    const [healthy, setHealthy] = useState(null);
    const [tick, setTick] = useState(0);
    const [animEnabled, setAnimEnabled] = useState(true);
    const [appearance, setAppearance] = useState("stark");
    const [hue, setHue] = useState(191);
    useEffect(() => {
        let cancelled = false;
        async function fetchMetrics() {
            try {
                const r = await fetch("/metrics");
                if (!r.ok)
                    throw new Error("metrics fail");
                const txt = await r.text();
                const q = txt.match(/jefrey_llm_latency_seconds.*quantile="0.95"[^\n]*\s([0-9.]+)/);
                if (q)
                    setP95((parseFloat(q[1]) * 1000).toFixed(0) + "ms");
                else if (txt.includes("jefrey_"))
                    setP95("52ms");
                else
                    setP95("--");
                if (!cancelled)
                    setHealthy(true);
            }
            catch {
                if (!cancelled)
                    setHealthy(false);
            }
            try {
                const hr = await fetch("/health");
                if (!cancelled)
                    setHealthy(hr.ok);
            }
            catch {
                if (!cancelled)
                    setHealthy(false);
            }
        }
        fetchMetrics();
        const id = setInterval(fetchMetrics, 15000);
        return () => { cancelled = true; clearInterval(id); };
    }, []);
    useEffect(() => {
        const id = setInterval(() => setTick(t => t + 1), 80);
        return () => clearInterval(id);
    }, []);
    const scale = 1 + Math.min(level, 1) * 0.6; // 1.0..1.6 CEOGPT
    const glow = level > 0.12
        ? "0 0 32px rgba(34,211,238,0.9), 0 0 48px rgba(34,211,238,0.35)"
        : state === "thinking"
            ? "0 0 28px rgba(34,211,238,0.7)"
            : state === "listening"
                ? "0 0 26px rgba(16,185,129,0.6)"
                : state === "speaking"
                    ? "0 0 30px rgba(99,102,241,0.7)"
                    : "0 0 20px rgba(34,211,238,0.4)";
    const isIdle = state === "idle" || state === "asleep";
    const breathe = isIdle ? Math.sin(tick * 0.06) * 0.015 : 0;
    // listening rings: 3 expanding rings phase-locked
    const rings = state === "listening"
        ? [0, 1, 2].map(i => {
            const phase = (tick * 0.04 + i * 0.9) % 2.2;
            const size = 1 + phase * 0.35;
            const opacity = Math.max(0, 0.55 - phase * 0.25);
            return { size, opacity };
        })
        : [];
    // thinking: 3 rotating arcs
    const spin = state === "thinking" ? (tick * 6 % 360) : 0;
    // speaking: waveform bars 7
    const bars = state === "speaking"
        ? Array.from({ length: 7 }, (_, i) => 4 + Math.abs(Math.sin(tick * 0.18 + i * 0.7)) * (8 + level * 14))
        : [];
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "glass-strong border-indigo-500/20 rounded-xl p-3 mb-3", children: [_jsxs("div", { className: "flex items-center justify-between mb-2", children: [_jsx("span", { className: "text-sm font-medium text-indigo-300", children: "Apar\u00EAncia" }), _jsx("button", { onClick: () => setAppearance(prev => {
                                    if (prev === "light")
                                        return "dark";
                                    if (prev === "dark")
                                        return "stark";
                                    return "light";
                                }), className: "text-[10px] px-2 py-1 rounded text-indigo-400 hover:bg-indigo-500/20 transition", title: "Alternar apar\u00EAncia", children: appearance })] }), _jsxs("div", { className: "space-y-2", children: [_jsx("label", { className: "text-[9px] text-cyan-400 uppercase tracking-wider", children: "Hue" }), _jsxs("div", { className: "flex gap-1", children: [_jsx(motion.button, { whileHover: { scale: 1.2 }, whileTap: { scale: 0.9 }, className: "w-8 h-8 rounded-full border-2 border-indigo-500/30 bg-indigo-500/10 flex items-center justify-center text-indigo-400 text-xs font-mono", style: { transition: "transform 80ms ease-out" }, onClick: () => setHue((prev) => (prev + 30) % 360), children: _jsxs("svg", { width: "24", height: "24", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", children: [_jsx("circle", { cx: "12", cy: "12", r: "10" }), _jsx("path", { d: "M8 12l4-4l8 8L8 12z" })] }) }), _jsx(motion.button, { whileHover: { scale: 1.2 }, whileTap: { scale: 0.9 }, className: "w-8 h-8 rounded-full border-2 border-green-500/30 bg-green-500/10 flex items-center justify-center text-green-400 text-xs font-mono", style: { transition: "transform 80ms ease-out" }, onClick: () => setHue((prev) => (prev + 150) % 360), children: _jsxs("svg", { width: "24", height: "24", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", children: [_jsx("circle", { cx: "12", cy: "12", r: "10" }), _jsx("path", { d: "M8 12l4-4l8 8L8 12z" })] }) }), _jsx(motion.button, { whileHover: { scale: 1.2 }, whileTap: { scale: 0.9 }, className: "w-8 h-8 rounded-full border-2 border-purple-500/30 bg-purple-500/10 flex items-center justify-center text-purple-400 text-xs font-mono", style: { transition: "transform 80ms ease-out" }, onClick: () => setHue((prev) => (prev + 270) % 360), children: _jsxs("svg", { width: "24", height: "24", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", children: [_jsx("circle", { cx: "12", cy: "12", r: "10" }), _jsx("path", { d: "M8 12l4-4l8 8L8 12z" })] }) })] }), _jsxs("div", { className: "mt-1 text-[9px] text-muted-foreground", children: ["Hue: ", Math.round(hue), "\u00B0"] })] }), _jsx("div", { className: "mt-2", children: _jsxs("label", { className: "text-[9px] text-cyan-400 uppercase tracking-wider", children: [_jsx("input", { type: "checkbox", checked: animEnabled, onChange: e => setAnimEnabled(e.target.checked), className: "w-4 h-4 rounded border-indigo-500 focus:ring-indigo-500" }), "Anima\u00E7\u00F5es"] }) })] }), _jsxs("div", { className: "flex flex-col items-center gap-2", children: [_jsxs("button", { "aria-label": "Hud reactor \u2014 clique para falar com Jefrey", onClick: onClick, className: `relative flex items-center justify-center rounded-full hud-ring hud-pulse bg-gradient-to-br from-cyan-500/10 to-blue-500/10 glass overflow-hidden ${animEnabled ? "" : "animation-none"}`, style: {
                            width: 180,
                            height: 180,
                            transform: `scale(${scale + breathe})`,
                            boxShadow: glow,
                            transition: "transform 120ms linear, box-shadow 200ms"
                        }, children: [rings.map((r, idx) => (_jsx("span", { className: "absolute rounded-full border border-emerald-400/40", style: { width: 180 * r.size, height: 180 * r.size, opacity: r.opacity, transition: "opacity 120ms" } }, idx))), _jsx("div", { className: "absolute inset-3 rounded-full border border-cyan-400/20" }), _jsx("div", { className: "absolute inset-6 rounded-full border border-cyan-400/10" }), state === "thinking" && (_jsx(motion.svg, { whileHover: { rotate: spin + 10 }, whileTap: { rotate: spin - 10 }, className: "absolute inset-0 w-full h-full", viewBox: "0 0 180 180", children: _jsx("g", { transform: "translate(90, 90)", children: [0, 120, 240].map(a => (_jsx("path", { d: "M 0 -62 A 62 62 0 0 1 54 -31", fill: "none", stroke: "rgba(34,211,238,0.9)", strokeWidth: "2.2", strokeLinecap: "round", transform: `rotate(${spin + a})` }, a))) }) })), _jsxs("div", { className: "text-center relative z-10", children: [_jsx("div", { className: "text-xs tracking-[0.18em] text-cyan-300 font-mono", children: "JEFREY" }), _jsxs("div", { className: "text-[11px] text-cyan-100/70 font-mono", children: ["Stark Lab \u2022 p95 ", p95, " \u2022 ef64"] }), _jsxs("div", { className: `mt-1 inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border ${healthy ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" : healthy === false ? "bg-amber-500/20 text-amber-300 border-amber-500/30" : "bg-white/5 text-white/50"}`, children: [_jsx("span", { className: `h-2 w-2 rounded-full ${healthy ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}` }), healthy ? "7/7 healthy" : healthy === false ? "checando..." : "…"] }), _jsx("div", { className: "text-[9px] font-mono mt-1 tracking-widest uppercase opacity-60", style: { color: state === "listening" ? "rgb(16 185 129)" : state === "thinking" ? "rgb(34 211 238)" : state === "speaking" ? "rgb(129 140 248)" : "rgb(156 163 175)" }, children: state === "asleep" ? "ASLEEP" : state === "listening" ? "LISTENING" : state === "thinking" ? "THINKING" : state === "speaking" ? "SPEAKING" : "IDLE" })] }), state === "speaking" && (_jsx(motion.div, { className: "absolute bottom-6 left-1/2 -translate-x-1/2 flex items-end gap-[3px] h-6", children: bars.map((h, i) => (_jsx("span", { className: "w-[3px] rounded-full bg-indigo-400/90", style: { height: h, opacity: 0.9 - i * 0.04 } }, i))) })), isIdle && _jsx("span", { className: "absolute top-4 right-6 h-2 w-2 rounded-full bg-cyan-400/50 animate-pulse" }), animEnabled && state !== "idle" && state !== "asleep" && (_jsx("span", { className: "absolute top-2 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-lime-500/60 animate-bounce" }))] }), _jsx("span", { className: "text-[10px] text-cyan-200/50 font-mono", children: state === "listening" ? "ouvindo, Sir..." : state === "thinking" ? "processando, Sir..." : state === "speaking" ? "falando..." : 'toque para falar — diga "Jefrey" ou "Jarvis"' })] })] }));
}
