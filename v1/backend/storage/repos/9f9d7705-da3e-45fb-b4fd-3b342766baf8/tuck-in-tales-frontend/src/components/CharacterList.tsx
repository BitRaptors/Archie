import React, { useState, useEffect } from 'react';
import { api } from '@/api/client';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ExclamationTriangleIcon, Pencil1Icon, TrashIcon } from '@radix-ui/react-icons';
import { ConfirmationDialog } from './ConfirmationDialog';
import { toast } from 'sonner';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { getPublicAvatarUrl } from '@/utils/supabaseUtils';
import { useNavigate } from 'react-router-dom';

// Define an interface for the character data expected from the API
// Based on Character model in backend src/models/character.py
interface Character {
  id: string; // UUID as string
  family_id: string;
  name: string;
  bio?: string; // Updated field name
  birth_date?: string; // Date as string
  avatar_url?: string;
  photo_paths?: string[]; // Updated field name
  created_at: string; // Timestamp as string
  updated_at: string;
}

export default function CharacterList() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const navigate = useNavigate();

  const loadCharacters = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.fetchCharacters();
      setCharacters(data || []);
    } catch (err: any) {
      console.error("Error fetching characters:", err);
      setError(err.response?.data?.detail || err.message || 'Failed to load characters.');
      toast.error("Failed to load characters");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCharacters();
  }, []);

  const handleEdit = (characterId: string) => {
    console.log(`Edit character requested: ${characterId}`);
    toast.info(`Edit functionality for ${characterId} not implemented yet.`);
  };

  const handleCardClick = (characterId: string) => {
    navigate(`/characters/${characterId}`);
  };

  const handleDelete = async (characterId: string) => {
    setActionLoading(prev => ({ ...prev, [characterId]: true }));
    setError(null);
    try {
      await api.deleteCharacter(characterId);
      setCharacters(prevChars => prevChars.filter(char => char.id !== characterId));
      toast.success("Character deleted successfully!");
    } catch (err: any) {
      console.error("Error deleting character:", err);
      const deleteError = err.response?.data?.detail || err.message || 'Failed to delete character.';
      setError(deleteError);
      toast.error(deleteError);
    } finally {
      setActionLoading(prev => ({ ...prev, [characterId]: false }));
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-4 w-3/4" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error && characters.length === 0) {
    return (
      <Alert variant="destructive">
        <ExclamationTriangleIcon className="h-4 w-4" />
        <AlertTitle>Error Loading Characters</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {characters.map((char) => {
        const publicUrl = getPublicAvatarUrl(char.avatar_url);
        return (
          <Card 
              key={char.id} 
              className="cursor-pointer hover:shadow-md transition-shadow flex flex-col" 
              onClick={() => handleCardClick(char.id)}
          >
            <CardHeader className="flex flex-row items-center space-x-4">
              <Avatar className="h-12 w-12">
                 <AvatarImage src={publicUrl || undefined} alt={char.name} />
                 <AvatarFallback>{char.name?.charAt(0).toUpperCase() || 'C'}</AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <CardTitle className="text-lg">{char.name}</CardTitle>
              </div>
            </CardHeader>
          </Card>
        )
      })}

      {characters.length === 0 && !loading && (
        <div className="col-span-full text-center p-6 bg-muted rounded-lg">
            <p className="text-sm text-muted-foreground">No characters found. Click 'Add Character' to create one!</p>
        </div>
      )}

      {error && characters.length === 0 && (
            <Alert variant="destructive" className="col-span-full">
                <ExclamationTriangleIcon className="h-4 w-4" />
                <AlertTitle>Error Loading</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
            </Alert>
        )}
    </div>
  );
} 