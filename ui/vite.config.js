import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
export default defineConfig({
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    server: {
        port: 5173,
        proxy: {
            "/health": "http://localhost:8000",
            "/chat": "http://localhost:8000",
            "/memory": "http://localhost:8000",
            "/approvals": "http://localhost:8000",
            "/metrics": "http://localhost:8000"
        }
    },
    build: {
        outDir: "../src/jefrey/static",
        emptyOutDir: true,
        chunkSizeWarningLimit: 600,
        rollupOptions: {
            output: {
                manualChunks: {
                    vendor: ["react", "react-dom", "react-router-dom"],
                    query: ["@tanstack/react-query"],
                    charts: ["recharts"],
                    ui: ["clsx", "tailwind-merge", "class-variance-authority", "lucide-react"]
                }
            }
        }
    }
});
