import { Moon, Sun } from "lucide-react"
import { useTheme } from "../contexts/ThemeProvider"
import { motion } from "framer-motion"

export function ThemeToggle() {
    const { theme, setTheme } = useTheme()

    return (
        <button
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            className="relative p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
            <motion.div
                initial={false}
                animate={{
                    scale: theme === "light" ? 1 : 0,
                    rotate: theme === "light" ? 0 : 90,
                    opacity: theme === "light" ? 1 : 0
                }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0 m-auto flex items-center justify-center text-slate-700"
            >
                <Sun className="h-5 w-5" />
            </motion.div>

            <motion.div
                initial={false}
                animate={{
                    scale: theme === "dark" ? 1 : 0,
                    rotate: theme === "dark" ? 0 : -90,
                    opacity: theme === "dark" ? 1 : 0
                }}
                transition={{ duration: 0.2 }}
                className="flex items-center justify-center text-slate-200"
            >
                <Moon className="h-5 w-5" />
            </motion.div>
            {/* Invisible spacer to maintain size */}
            <div className="w-5 h-5 opacity-0"></div>
        </button>
    )
}
