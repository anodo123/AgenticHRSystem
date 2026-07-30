import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from '../components/AppLayout'
import App from '../App'

describe('application components', () => {
  it('renders readable workflow status', () => {
    render(<StatusBadge value="WAITING_FOR_APPROVAL" />)
    expect(screen.getByText('WAITING FOR APPROVAL')).toBeInTheDocument()
  })

  it('protects operations routes when signed out', () => {
    render(<MemoryRouter initialEntries={['/workflows']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })
})
