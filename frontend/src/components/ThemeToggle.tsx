import { Moon, Sun } from "lucide-react"
import { useTheme } from "../contexts/ThemeProvider"
import { motion } from "framer-motion"

interface ThemeToggleProps {
    size?: 'sm' | 'md';
}

export function ThemeToggle({ size = 'md' }: ThemeToggleProps) {
    const { theme, setTheme } = useTheme()
    const iconSize = size === 'sm' ? "h-3.5 w-3.5" : "h-5 w-5"

    return (
        <button
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            className={`flex relative rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors ${size === 'sm' ? 'p-1.5' : 'p-2'}`}
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
                <Sun className={iconSize} />
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
                <Moon className={iconSize} />
            </motion.div>
            {/* Invisible spacer to maintain size */}
            <div className={`${size === 'sm' ? 'w-3.5 h-3.5' : 'w-5 h-5'} opacity-0`}></div>
        </button>
    )
}
