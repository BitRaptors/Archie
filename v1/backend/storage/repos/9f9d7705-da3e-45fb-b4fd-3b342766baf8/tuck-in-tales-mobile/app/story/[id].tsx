import { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  Image,
  Pressable,
  Modal,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
  StatusBar,
  Animated,
  PanResponder,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useStory } from '../../src/hooks/queries/useStory';
import type { StoryPageProgress } from '../../src/models/story';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const DISMISS_THRESHOLD = 150;

export default function StoryDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { data: story, isLoading, error } = useStory(id!);

  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null);
  const [imageErrors, setImageErrors] = useState<Set<number>>(new Set());

  const handleImageError = useCallback((pageNum: number) => {
    setImageErrors((prev) => new Set(prev).add(pageNum));
  }, []);

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#000" />
        <Text style={styles.loadingText}>Loading story...</Text>
      </View>
    );
  }

  if (error || !story) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>{error ? 'Failed to load story' : 'Story not found'}</Text>
        {error && <Text style={styles.errorDetail}>{error.message}</Text>}
        <Pressable style={styles.retryButton} onPress={() => router.back()}>
          <Text style={styles.retryButtonText}>Go Back</Text>
        </Pressable>
      </View>
    );
  }

  const formattedDate = new Date(story.created_at).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <View style={styles.container}>
      <StatusBar barStyle="dark-content" />

      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.backButton}>‹ Back</Text>
        </Pressable>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Title section */}
        <Text style={styles.title}>{story.title}</Text>
        <View style={styles.metaRow}>
          <Text style={styles.metaText}>{formattedDate}</Text>
          <Text style={styles.metaDot}>·</Text>
          <Text style={styles.metaText}>{story.language.toUpperCase()}</Text>
          {story.pages?.length > 0 && (
            <>
              <Text style={styles.metaDot}>·</Text>
              <Text style={styles.metaText}>{story.pages.length} pages</Text>
            </>
          )}
        </View>

        {/* Story pages */}
        {story.pages?.map((page, index) => (
          <StoryPageView
            key={page.page ?? index}
            page={page}
            index={index}
            hasImageError={imageErrors.has(page.page ?? index)}
            onImageError={handleImageError}
            onImagePress={setFullscreenImage}
          />
        ))}

        {/* End marker */}
        {story.pages?.length > 0 && (
          <View style={styles.endMarker}>
            <View style={styles.endLine} />
            <Text style={styles.endText}>The End</Text>
            <View style={styles.endLine} />
          </View>
        )}
      </ScrollView>

      {/* Fullscreen image viewer */}
      <FullscreenImageViewer
        imageUrl={fullscreenImage}
        onClose={() => setFullscreenImage(null)}
      />
    </View>
  );
}

function StoryPageView({
  page,
  index,
  hasImageError,
  onImageError,
  onImagePress,
}: {
  page: StoryPageProgress;
  index: number;
  hasImageError: boolean;
  onImageError: (pageNum: number) => void;
  onImagePress: (url: string) => void;
}) {
  const pageNum = page.page ?? index;

  return (
    <View style={styles.pageContainer}>
      {/* Page image */}
      {page.image_url && !hasImageError ? (
        <Pressable onPress={() => onImagePress(page.image_url!)}>
          <Image
            source={{ uri: page.image_url }}
            style={styles.pageImage}
            resizeMode="cover"
            onError={() => onImageError(pageNum)}
          />
        </Pressable>
      ) : page.image_url && hasImageError ? (
        <View style={styles.imagePlaceholder}>
          <Text style={styles.placeholderText}>Image unavailable</Text>
        </View>
      ) : null}

      {/* Page text */}
      {page.text && <Text style={styles.pageText}>{page.text}</Text>}

      {/* Characters on page */}
      {page.characters_on_page && page.characters_on_page.length > 0 && (
        <View style={styles.charactersRow}>
          {page.characters_on_page.map((name) => (
            <View key={name} style={styles.characterChip}>
              <Text style={styles.characterChipText}>{name}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

function FullscreenImageViewer({
  imageUrl,
  onClose,
}: {
  imageUrl: string | null;
  onClose: () => void;
}) {
  const translateY = useRef(new Animated.Value(0)).current;
  const backdropOpacity = useRef(new Animated.Value(1)).current;
  const imageScale = useRef(new Animated.Value(1)).current;

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, gestureState) =>
        Math.abs(gestureState.dy) > 5,
      onPanResponderMove: (_, gestureState) => {
        translateY.setValue(gestureState.dy);
        const progress = Math.min(Math.abs(gestureState.dy) / DISMISS_THRESHOLD, 1);
        backdropOpacity.setValue(1 - progress * 0.5);
        imageScale.setValue(1 - progress * 0.1);
      },
      onPanResponderRelease: (_, gestureState) => {
        if (Math.abs(gestureState.dy) > DISMISS_THRESHOLD) {
          const target = gestureState.dy > 0 ? SCREEN_HEIGHT : -SCREEN_HEIGHT;
          Animated.parallel([
            Animated.timing(translateY, { toValue: target, duration: 200, useNativeDriver: true }),
            Animated.timing(backdropOpacity, { toValue: 0, duration: 200, useNativeDriver: true }),
          ]).start(() => {
            // Reset values for next open
            translateY.setValue(0);
            backdropOpacity.setValue(1);
            imageScale.setValue(1);
            onClose();
          });
        } else {
          Animated.parallel([
            Animated.spring(translateY, { toValue: 0, useNativeDriver: true }),
            Animated.spring(backdropOpacity, { toValue: 1, useNativeDriver: true }),
            Animated.spring(imageScale, { toValue: 1, useNativeDriver: true }),
          ]).start();
        }
      },
    })
  ).current;

  if (!imageUrl) return null;

  return (
    <Modal transparent statusBarTranslucent animationType="fade" onRequestClose={onClose}>
      <Animated.View style={[styles.fullscreenBackdrop, { opacity: backdropOpacity }]}>
        {/* Close button */}
        <Pressable style={styles.closeButton} onPress={onClose} hitSlop={16}>
          <Text style={styles.closeButtonText}>✕</Text>
        </Pressable>

        <Animated.Image
          {...panResponder.panHandlers}
          source={{ uri: imageUrl }}
          style={[
            styles.fullscreenImage,
            {
              transform: [
                { translateY: translateY },
                { scale: imageScale },
              ],
            },
          ]}
          resizeMode="contain"
        />
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 24,
  },
  header: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 12,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  backButton: {
    fontSize: 18,
    color: '#000',
    fontWeight: '500',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 24,
    paddingBottom: 48,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#000',
    marginBottom: 8,
    lineHeight: 36,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 32,
  },
  metaText: {
    fontSize: 13,
    color: '#888',
  },
  metaDot: {
    fontSize: 13,
    color: '#ccc',
    marginHorizontal: 8,
  },
  pageContainer: {
    marginBottom: 32,
  },
  pageImage: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 12,
    backgroundColor: '#f0f0f0',
    marginBottom: 16,
  },
  imagePlaceholder: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 12,
    backgroundColor: '#f5f5f5',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  placeholderText: {
    fontSize: 14,
    color: '#999',
  },
  pageText: {
    fontSize: 18,
    lineHeight: 28,
    color: '#1a1a1a',
    letterSpacing: 0.2,
  },
  charactersRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 12,
  },
  characterChip: {
    backgroundColor: '#f0f0f0',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  characterChipText: {
    fontSize: 12,
    color: '#666',
  },
  endMarker: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    marginBottom: 8,
  },
  endLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#e0e0e0',
  },
  endText: {
    fontSize: 14,
    color: '#999',
    fontStyle: 'italic',
    marginHorizontal: 16,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#666',
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
  fullscreenBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  fullscreenImage: {
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT * 0.75,
  },
  closeButton: {
    position: 'absolute',
    top: 56,
    right: 20,
    zIndex: 10,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
});
