import { View, Text } from 'react-native';
import { Link } from 'expo-router';

export default function NotFoundScreen() {
  return (
    <View className="flex-1 bg-background justify-center items-center p-6">
      <Text className="text-2xl font-bold text-foreground mb-4">
        404 - Not Found
      </Text>

      <Text className="text-muted-foreground mb-6 text-center">
        This page doesn't exist.
      </Text>

      <Link href="/(tabs)" className="text-primary underline">
        Go to Home
      </Link>
    </View>
  );
}
