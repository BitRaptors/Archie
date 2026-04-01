import { View, Text, StyleSheet } from 'react-native';

export default function MemoriesScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Memories</Text>

      <Text style={styles.description}>
        Log daily memories for your bedtime stories.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    padding: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#000',
    marginBottom: 16,
  },
  description: {
    fontSize: 14,
    color: '#666',
  },
});
