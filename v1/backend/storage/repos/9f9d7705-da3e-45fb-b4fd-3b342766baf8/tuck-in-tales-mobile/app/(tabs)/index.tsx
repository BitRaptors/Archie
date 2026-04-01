import { View, Text, Pressable, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import { useAuth } from '../../src/context/AuthContext';
import { signOut } from 'firebase/auth';
import { auth } from '../../src/config/firebase';
import { useRouter } from 'expo-router';
import { useFamilyDetails } from '../../src/hooks/queries/useFamilyDetails';
import { useStories } from '../../src/hooks/queries/useStories';
import type { StoryBasic } from '../../src/models/story';

export default function StoriesScreen() {
  const { currentUser } = useAuth();
  const router = useRouter();
  const familyQuery = useFamilyDetails();
  const storiesQuery = useStories();

  const handleSignOut = async () => {
    await signOut(auth);
    router.replace('/(auth)/login');
  };

  const handleStoryPress = (storyId: string) => {
    router.push(`/story/${storyId}`);
  };

  const handleGenerateStory = () => {
    // TODO: Navigate to story generation modal
    console.log('Generate new story');
  };

  // Render loading state
  if (familyQuery.isLoading || storiesQuery.isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#000" />
        <Text style={styles.loadingText}>Loading stories...</Text>
      </View>
    );
  }

  // Render error state
  if (familyQuery.error || storiesQuery.error) {
    const error = familyQuery.error || storiesQuery.error;
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Stories</Text>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>Error loading data</Text>
          <Text style={styles.errorDetail}>{error?.message}</Text>
          <Pressable
            style={styles.retryButton}
            onPress={() => {
              familyQuery.refetch();
              storiesQuery.refetch();
            }}
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
        <Pressable style={styles.signOutButton} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </Pressable>
      </View>
    );
  }

  // Check if user has no family
  if (!familyQuery.data) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Stories</Text>
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>👨‍👩‍👧‍👦</Text>
          <Text style={styles.emptyTitle}>No Family Yet</Text>
          <Text style={styles.emptyDescription}>
            Create or join a family to start generating bedtime stories.
          </Text>
          <Pressable style={styles.primaryButton} onPress={() => console.log('Create family')}>
            <Text style={styles.primaryButtonText}>Create Family</Text>
          </Pressable>
          <Pressable style={styles.secondaryButton} onPress={() => console.log('Join family')}>
            <Text style={styles.secondaryButtonText}>Join Family</Text>
          </Pressable>
        </View>
        <Pressable style={styles.signOutButton} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </Pressable>
      </View>
    );
  }

  // Render family header and stories list
  const stories = storiesQuery.data || [];

  return (
    <View style={styles.container}>
      {/* Family header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.familyLabel}>Family</Text>
          <Text style={styles.familyName}>{familyQuery.data.name}</Text>
        </View>
        <Pressable style={styles.signOutButton} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </Pressable>
      </View>

      {/* Stories list */}
      {stories.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>📚</Text>
          <Text style={styles.emptyTitle}>No Stories Yet</Text>
          <Text style={styles.emptyDescription}>
            Generate your first bedtime story to get started.
          </Text>
          <Pressable style={styles.primaryButton} onPress={handleGenerateStory}>
            <Text style={styles.primaryButtonText}>Generate Story</Text>
          </Pressable>
        </View>
      ) : (
        <>
          <View style={styles.headerRow}>
            <Text style={styles.title}>Your Stories</Text>
            <Pressable style={styles.addButton} onPress={handleGenerateStory}>
              <Text style={styles.addButtonText}>+ New</Text>
            </Pressable>
          </View>
          <FlatList
            data={stories}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => (
              <StoryCard story={item} onPress={handleStoryPress} />
            )}
            contentContainerStyle={styles.listContent}
          />
        </>
      )}
    </View>
  );
}

// Story card component
function StoryCard({ story, onPress }: { story: StoryBasic; onPress: (id: string) => void }) {
  // Format date
  const date = new Date(story.created_at);
  const formattedDate = date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });

  // Status badge color
  const statusColor = getStatusColor(story.status);

  return (
    <Pressable
      style={styles.storyCard}
      onPress={() => onPress(story.id)}
    >
      <View style={styles.storyCardContent}>
        <Text style={styles.storyTitle}>{story.title}</Text>
        <View style={styles.storyMeta}>
          <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
            <Text style={styles.statusText}>{story.status}</Text>
          </View>
          <Text style={styles.storyDate}>{formattedDate}</Text>
          <Text style={styles.storyLanguage}>{story.language.toUpperCase()}</Text>
        </View>
      </View>
      <Text style={styles.chevron}>›</Text>
    </Pressable>
  );
}

// Helper function for status colors
function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'complete':
    case 'completed':
      return '#10b981'; // green
    case 'generating':
    case 'outlining':
    case 'writing':
      return '#f59e0b'; // orange
    case 'failed':
      return '#ef4444'; // red
    default:
      return '#6b7280'; // gray
  }
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e5e5',
  },
  familyLabel: {
    fontSize: 12,
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  familyName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#000',
    marginTop: 4,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
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
    marginBottom: 12,
    minWidth: 200,
  },
  primaryButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
  },
  secondaryButton: {
    backgroundColor: '#fff',
    borderWidth: 2,
    borderColor: '#000',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 32,
    alignItems: 'center',
    minWidth: 200,
  },
  secondaryButtonText: {
    color: '#000',
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
  signOutButton: {
    backgroundColor: '#ef4444',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 16,
    alignItems: 'center',
  },
  signOutText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 14,
  },
  listContent: {
    paddingBottom: 16,
  },
  storyCard: {
    backgroundColor: '#f9fafb',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: '#e5e5e5',
  },
  storyCardContent: {
    flex: 1,
  },
  storyTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
    marginBottom: 8,
  },
  storyMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  statusText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  storyDate: {
    fontSize: 12,
    color: '#666',
  },
  storyLanguage: {
    fontSize: 11,
    color: '#666',
    fontWeight: '500',
  },
  chevron: {
    fontSize: 24,
    color: '#999',
    marginLeft: 8,
  },
});
