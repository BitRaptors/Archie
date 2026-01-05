---
id: shared-anti-patterns
title: Common Anti-Patterns
category: shared
tags: [anti-patterns, violations, common-mistakes]
related: [backend-layers, frontend-structure]
---

# Common Anti-Patterns

## Backend Anti-Patterns

### Layer Violations

**Violation**: Domain layer importing from infrastructure
```python
# ❌ WRONG - domain/entities/user.py
from infrastructure.persistence.supabase_user_repository import SupabaseUserRepository

class User:
    def save(self):
        repo = SupabaseUserRepository(...)  # Domain knows about infrastructure!
```

**Correct**: Domain defines interface, infrastructure implements
```python
# ✅ CORRECT - domain/interfaces/repositories.py
class IUserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> User:
        ...

# domain/entities/user.py - no infrastructure imports
# infrastructure/persistence/supabase_user_repository.py - implements IUserRepository
```

### Controller Doing Business Logic

**Violation**: Controller contains business rules
```python
# ❌ WRONG
@router.post("/users")
async def create_user(request: CreateUserRequest):
    if request.email.endswith("@admin.com"):
        raise HTTPException(400, "Admin emails not allowed")  # Business rule in controller!
    # ... database calls directly
```

**Correct**: Controller delegates to service
```python
# ✅ CORRECT
@router.post("/users")
async def create_user(request: CreateUserRequest, service: UserService = Depends(...)):
    user = await service.create_user(request.email, request.name)  # Service handles rules
    return UserResponse.from_entity(user)
```

## Frontend Anti-Patterns

### Business Logic in Components

**Violation**: Component contains business logic
```typescript
// ❌ WRONG
function UserList() {
  const [users, setUsers] = useState([])
  
  useEffect(() => {
    fetch('/api/users')
      .then(res => res.json())
      .then(data => {
        // Business logic in component!
        const filtered = data.filter(u => u.status === 'active')
        setUsers(filtered)
      })
  }, [])
}
```

**Correct**: Use hooks for business logic
```typescript
// ✅ CORRECT
function UserList() {
  const { data: users } = useUsersQuery({ status: 'active' })  // Logic in hook
  return <div>{/* render */}</div>
}
```

### Direct Service Calls in Components

**Violation**: Component directly imports service implementation
```typescript
// ❌ WRONG
import { firebaseAuthService } from '@/services/firebase/auth'

function LoginButton() {
  const handleClick = () => {
    firebaseAuthService.signInWithGoogle()  // Tightly coupled to Firebase
  }
}
```

**Correct**: Use service abstraction
```typescript
// ✅ CORRECT
import { useAuthService } from '@/context/services'

function LoginButton() {
  const authService = useAuthService()  // Swappable implementation
  const handleClick = () => {
    authService.signInWithGoogle()
  }
}
```

### Context Without Consumer Hook

**Violation**: Direct useContext calls everywhere
```typescript
// ❌ WRONG - Every component does this
const user = useContext(AuthContext)?.user
const isLoading = useContext(AuthContext)?.isLoading
```

**Correct**: Create consumer hook
```typescript
// ✅ CORRECT
export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}

// Usage
const { user, isLoading } = useAuth()
```


