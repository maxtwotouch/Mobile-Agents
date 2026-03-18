// Role visual identities — icons as inline SVG paths, colors per role

export interface RoleVisual {
  icon: string   // SVG path d attribute (24x24 viewBox)
  color: string  // accent color
  label: string
}

export const roleVisuals: Record<string, RoleVisual> = {
  planner: {
    icon: 'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z',
    color: '#c9a94e',
    label: 'Planner',
  },
  architect: {
    icon: 'M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z',
    color: '#7b8ec9',
    label: 'Architect',
  },
  developer: {
    icon: 'M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z',
    color: '#6b9a5c',
    label: 'Developer',
  },
  reviewer: {
    icon: 'M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
    color: '#c9a04e',
    label: 'Reviewer',
  },
  qa: {
    icon: 'M20 8h-2.81c-.45-.78-1.07-1.45-1.82-1.96L17 4.41 15.59 3l-2.17 2.17C12.96 5.06 12.49 5 12 5s-.96.06-1.41.17L8.41 3 7 4.41l1.62 1.63C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8zm-6 8h-4v-2h4v2zm0-4h-4v-2h4v2z',
    color: '#c45c4a',
    label: 'QA',
  },
  release_engineer: {
    icon: 'M9.19 6.35c-2.04 2.29-3.44 5.58-3.57 5.89L2 10.69l4.05-4.05c.47-.47 1.15-.68 1.81-.55l1.33.26zM11.17 17s3.74-1.55 5.89-3.7c5.4-5.4 4.5-9.62 4.21-10.57-.95-.3-5.17-1.19-10.57 4.21C8.55 9.09 7 12.83 7 12.83L11.17 17zm6.48-2.19c-2.29 2.04-5.58 3.44-5.89 3.57L13.31 22l4.05-4.05c.47-.47.68-1.15.55-1.81l-.26-1.33zM9 18c0 .83-.34 1.58-.88 2.12C7.94 20.3 7.62 20.5 7 21c-1 .5-3 1-3 1s.5-2 1-3c.5-.62.7-.94.88-1.12A2.999 2.999 0 019 18zm-1.5-1.5c-.28 0-.5.22-.5.5s.22.5.5.5.5-.22.5-.5-.22-.5-.5-.5z',
    color: '#5c8ab0',
    label: 'Release',
  },
}

export function getRoleVisual(roleName: string | null): RoleVisual | null {
  if (!roleName) return null
  return roleVisuals[roleName] || null
}

// Status config
export const statusConfig: Record<string, { label: string; color: string }> = {
  pending:      { label: 'Pending',  color: '#5c564e' },
  running:      { label: 'Running',  color: '#6b9a5c' },
  paused:       { label: 'Paused',   color: '#c9a94e' },
  needs_review: { label: 'Review',   color: '#c45c4a' },
  completed:    { label: 'Done',     color: '#5c8ab0' },
  failed:       { label: 'Failed',   color: '#c45c4a' },
  draft:        { label: 'Draft',    color: '#8f846f' },
  ready:        { label: 'Ready',    color: '#5c564e' },
  in_progress:  { label: 'Working',  color: '#6b9a5c' },
  waiting_for_user: { label: 'Waiting', color: '#c9a94e' },
  blocked:      { label: 'Blocked',  color: '#c45c4a' },
  approved:     { label: 'Approved', color: '#5c8ab0' },
  cancelled:    { label: 'Cancelled', color: '#8f846f' },
}
