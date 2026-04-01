import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import CharacterList from '@/components/CharacterList';
import { PlusIcon } from '@radix-ui/react-icons';

export default function CharactersPage() {
  const navigate = useNavigate();

  const handleAddCharacter = () => {
    navigate('/characters/create');
  };

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Characters</h1>
        <Button onClick={handleAddCharacter}>
          <PlusIcon className="mr-2 h-4 w-4" /> Add Character
        </Button>
      </div>

      <CharacterList />
    </div>
  );
} 