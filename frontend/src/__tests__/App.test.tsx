import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText('GeoLux')).toBeInTheDocument();
  });

  it('renders navigation items', () => {
    render(<App />);
    const navItems = ['Hypotheses', 'Classification', 'MPC', 'Hardware', 'Launchpad', 'Stability', 'Admin'];
    for (const item of navItems) {
      expect(screen.getByRole('link', { name: item })).toBeInTheDocument();
    }
  });

  it('renders footer', () => {
    render(<App />);
    expect(screen.getByText(/Governed Agentic Inference/)).toBeInTheDocument();
  });
});
