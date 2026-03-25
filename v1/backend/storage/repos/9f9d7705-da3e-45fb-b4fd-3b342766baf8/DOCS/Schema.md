# Database Schema for Tuck-In Tales

## Tables
- **families**
  - `id`: uuid (primary key)
  - `name`: text
- **users**
  - `id`: uuid (primary key)
  - `email`: text
  - `family_id`: uuid (foreign key to `families.id`)
- **characters**
  - `id`: uuid (primary key)
  - `family_id`: uuid (foreign key to `families.id`)
  - `name`: text
  - `bio`: text
  - `photo_url`: text
  - `avatar_url`: text
  - `birth_date`: date
- **stories**
  - `id`: uuid (primary key)
  - `family_id`: uuid (foreign key to `families.id`)
  - `title`: text
  - `pages`: jsonb (array of {text, image_url})
  - `language`: text
  - `created_at`: timestamp
- **memories**
  - `id`: uuid (primary key)
  - `family_id`: uuid (foreign key to `families.id`)
  - `text`: text
  - `date`: date
  - `embedding`: vector(1536) (for similarity search)

## Relationships
- A family has many users, characters, stories, and memories.
- Users, characters, stories, and memories belong to one family.