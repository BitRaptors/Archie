import { Tabs } from 'expo-router';
import { View, Text } from 'react-native';

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#fff',
          borderTopWidth: 1,
          borderTopColor: '#e5e5e5',
        },
        tabBarActiveTintColor: '#000',
        tabBarInactiveTintColor: '#999',
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Stories',
          tabBarIcon: ({ color }) => (
            <View><Text style={{ color }}>📚</Text></View>
          ),
        }}
      />
      <Tabs.Screen
        name="characters"
        options={{
          title: 'Characters',
          tabBarIcon: ({ color }) => (
            <View><Text style={{ color }}>👥</Text></View>
          ),
        }}
      />
      <Tabs.Screen
        name="memories"
        options={{
          title: 'Memories',
          tabBarIcon: ({ color }) => (
            <View><Text style={{ color }}>💭</Text></View>
          ),
        }}
      />
    </Tabs>
  );
}
