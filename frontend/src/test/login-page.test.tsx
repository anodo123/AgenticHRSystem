import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { LoginPage } from '../pages/LoginPage'
import { useAuthStore } from '../store/auth'

describe('login page', () => {
  it('authenticates and persists the returned identity', async () => {
    vi.spyOn(api, 'post').mockResolvedValueOnce({ data: {
      access_token: 'access-token', refresh_token: 'refresh-token',
      username: 'admin', email: 'admin@example.com',
      full_name: 'System Admin', roles: ['SYSTEM_ADMIN'],
    } })
    render(<QueryClientProvider client={new QueryClient()}>
      <MemoryRouter><LoginPage /></MemoryRouter>
    </QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: /sign in securely/i }))
    await waitFor(() => expect(useAuthStore.getState().accessToken).toBe('access-token'))
    expect(useAuthStore.getState().user?.full_name).toBe('System Admin')
  })
})
