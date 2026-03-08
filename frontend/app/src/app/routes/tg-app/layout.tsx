/**
 * Telegram Mini App layout — strips admin shell, uses Telegram CSS vars.
 */
import { Outlet } from '@tanstack/react-router'

export function TgAppLayout() {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--tg-theme-bg-color, #fff)',
        color: 'var(--tg-theme-text-color, #000)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        padding: '12px 16px',
      }}
    >
      <Outlet />
    </div>
  )
}
