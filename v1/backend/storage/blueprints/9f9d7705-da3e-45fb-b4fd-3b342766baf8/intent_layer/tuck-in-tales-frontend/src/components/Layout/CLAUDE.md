# Layout/
> Layout wrapper providing fixed sidebar navigation + main content area with responsive spacing for authenticated app views.

## Patterns

- Sidebar is fixed positioned (left-0 top-0) with w-60; main content uses pl-60 to prevent overlap
- Navigation items stored as data array with icon components, rendered dynamically with isActive state from useLocation
- Button component uses asChild prop to wrap React Router Link while preserving styling and active states
- Icons imported from lucide-react and rendered inline via {item.icon} — requires uppercase export names
- Logout handler uses Firebase signOut + navigate redirect; loading state prevents double-clicks
- currentUser from AuthContext displayed as truncated email in sidebar header for user context

## Navigation

**Parent:** [`components/`](../CLAUDE.md)
**Peers:** [`Auth/`](../Auth/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md) | [`ui/`](../ui/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `AppLayout.tsx` | Root layout wrapper with sidebar + main flex container | Change pl-60 if sidebar width adjusts; children render as main content |
| `Sidebar.tsx` | Fixed navigation sidebar with auth user display and logout | Add routes to navItems array; icon must be React component in lucide-react |

## Key Imports

- `import { Link, useNavigate, useLocation } from 'react-router-dom'`
- `import { useAuth } from '@/context/AuthContext'`
- `import { signOut } from 'firebase/auth'`

## Add new navigation route to sidebar

1. Import icon from lucide-react (e.g., BarChart3)
2. Add {name: 'Label', path: '/route', icon: BarChart3} to navItems array
3. Verify route exists in app router; test active state on pathname match

## Usage Examples

### Navigation item with icon rendering
```jsx
const navItems = [{name: 'Stories', path: '/stories/list', icon: Sparkles}]
{navItems.map(item => (
  <Button asChild>
    <Link to={item.path}>
      <item.icon className="mr-2 h-4 w-4" />
      {item.name}
    </Link>
  </Button>
)))
```

## Don't

- Don't remove asChild from Button wrapping Link — breaks active styling and routing behavior
- Don't hardcode padding/margins for sidebar offset — use consistent pl-60 value in AppLayout main
- Don't inline icon logic in navItems — keep icon as component reference, render with {item.icon}

## Testing

- Navigation: Click each navItem, verify active variant applies to current route via useLocation
- Logout: Click logout button, verify signOut called and redirect to /login executes

## Why It's Built This Way

- Fixed sidebar + pl-60 offset: avoids layout shift, keeps nav always visible, simplifies scroll behavior
- Icons as data + dynamic render: scales navigation without touching JSX; icon prop is React component type, not string

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`
