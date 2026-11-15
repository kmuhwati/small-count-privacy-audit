import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// "./" keeps asset paths relative, so the build works at https://kmuhwati.github.io/<repo>/
export default defineConfig({
  plugins: [react()],
  base: "./",
});
