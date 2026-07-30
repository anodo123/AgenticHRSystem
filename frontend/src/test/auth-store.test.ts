import { describe, expect, it } from 'vitest'
import { useAuthStore } from '../store/auth'

describe('authentication state', () => {
  it('stores a session and clears it on logout', () => {
    useAuthStore.getState().login('access', 'refresh', {
      username: 'operator', email: 'operator@example.com',
      full_name: 'HR Operator', roles: ['HR_ADMIN'],
    })
    expect(useAuthStore.getState().accessToken).toBe('access')
    expect(useAuthStore.getState().user?.roles).toContain('HR_ADMIN')
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})
