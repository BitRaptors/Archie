import { View, Text, Pressable, StyleSheet, FlatList, ActivityIndicator, Image } from 'react-native';
import { useState } from 'react';
import { useFamilyDetails } from '../../src/hooks/queries/useFamilyDetails';
import { useCharacters } from '../../src/hooks/queries/useCharacters';
import type { Character } from '../../src/models/character';
import { getAvatarUrl } from '../../src/utils/supabaseUtils';

export default function CharactersScreen() {
  const familyQuery = useFamilyDetails();
  const charactersQuery = useCharacters();

  const handleCharacterPress = (characterId: string) => {
    // TODO: Navigate to character detail
    console.log('Navigate to character:', characterId);
  };

  const handleCreateCharacter = () => {
    // TODO: Navigate to character creation
    console.log('Create new character');
  };

  // Render loading state
  if (familyQuery.isLoading || charactersQuery.isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#000" />
        <Text style={styles.loadingText}>Loading characters...</Text>
      </View>
    );
  }

  // Render error state
  if (familyQuery.error || charactersQuery.error) {
    const error = familyQuery.error || charactersQuery.error;
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Characters</Text>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>Error loading data</Text>
          <Text style={styles.errorDetail}>{error?.message}</Text>
          <Pressable
            style={styles.retryButton}
            onPress={() => {
              familyQuery.refetch();
              charactersQuery.refetch();
            }}
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  // Check if user has no family
  if (!familyQuery.data) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Characters</Text>
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>👨‍👩‍👧‍👦</Text>
          <Text style={styles.emptyTitle}>No Family Yet</Text>
          <Text style={styles.emptyDescription}>
            Create or join a family to add characters for your stories.
          </Text>
        </View>
      </View>
    );
  }

  // Render characters list
  const characters = charactersQuery.data || [];

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.headerRow}>
        <Text style={styles.title}>Characters</Text>
        <Pressable style={styles.addButton} onPress={handleCreateCharacter}>
          <Text style={styles.addButtonText}>+ Add</Text>
        </Pressable>
      </View>

      {/* Characters list */}
      {characters.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>👤</Text>
          <Text style={styles.emptyTitle}>No Characters Yet</Text>
          <Text style={styles.emptyDescription}>
            Add characters to create personalized bedtime stories.
          </Text>
          <Pressable style={styles.primaryButton} onPress={handleCreateCharacter}>
            <Text style={styles.primaryButtonText}>Add First Character</Text>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={characters}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <CharacterCard character={item} onPress={handleCharacterPress} />
          )}
          contentContainerStyle={styles.listContent}
          numColumns={2}
          columnWrapperStyle={styles.columnWrapper}
        />
      )}
    </View>
  );
}

// Character card component
function CharacterCard({ character, onPress }: { character: Character; onPress: (id: string) => void }) {
  const [imageError, setImageError] = useState(false);

  // Get initials from name
  const initials = character.name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  // Convert storage path to public URL
  const avatarPublicUrl = getAvatarUrl(character.avatar_url);

  return (
    <Pressable
      style={styles.characterCard}
      onPress={() => onPress(character.id)}
    >
      {/* Avatar */}
      {avatarPublicUrl && !imageError ? (
        <Image
          source={{ uri: avatarPublicUrl }}
          style={styles.avatar}
          onError={() => setImageError(true)}
        />
      ) : (
        <View style={styles.avatarPlaceholder}>
          <Text style={styles.avatarInitials}>{initials}</Text>
        </View>
      )}

      {/* Character info */}
      <Text style={styles.characterName} numberOfLines={1}>
        {character.name}
      </Text>

      {character.birth_date && (
        <Text style={styles.characterAge}>
          Age {calculateAge(character.birth_date)}
        </Text>
      )}
    </Pressable>
  );
}

// Helper function to calculate age from birth date
function calculateAge(birthDate: string): number {
  const today = new Date();
  const birth = new Date(birthDate);
  let age = today.getFullYear() - birth.getFullYear();
  const monthDiff = today.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
    age--;
  }
  return age;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    padding: 24,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#000',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#666',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#ef4444',
    marginBottom: 8,
  },
  errorDetail: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 16,
  },
  retryButton: {
    backgroundColor: '#000',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 24,
  },
  retryButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#000',
    marginBottom: 8,
  },
  emptyDescription: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  primaryButton: {
    backgroundColor: '#000',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 32,
    alignItems: 'center',
    minWidth: 200,
  },
  primaryButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
  },
  addButton: {
    backgroundColor: '#000',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  addButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 14,
  },
  listContent: {
    paddingBottom: 16,
  },
  columnWrapper: {
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  characterCard: {
    backgroundColor: '#f9fafb',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#e5e5e5',
    width: '48%',
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    marginBottom: 12,
    backgroundColor: '#e5e5e5',
  },
  avatarPlaceholder: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#e5e5e5',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  avatarInitials: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#666',
  },
  characterName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
    textAlign: 'center',
    marginBottom: 4,
  },
  characterAge: {
    fontSize: 12,
    color: '#666',
  },
});
