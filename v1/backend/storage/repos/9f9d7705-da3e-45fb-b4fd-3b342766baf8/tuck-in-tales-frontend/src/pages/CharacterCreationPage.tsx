import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import MentionInput from '@/components/MentionInput';
import type { Character } from '@/models/character';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from '@/api/client';
import { toast } from 'sonner';
import { UploadIcon, Cross1Icon } from '@radix-ui/react-icons';

interface FileWithPreview extends File {
    preview: string;
}

export default function CharacterCreationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const prefill = (location.state as any)?.prefill;
  const [name, setName] = useState(prefill?.name || '');
  const [bio, setBio] = useState(prefill?.bio || '');
  const [birthDate, setBirthDate] = useState('');
  const [files, setFiles] = useState<FileWithPreview[]>([]);
  const [loading, setLoading] = useState(false);
  const [familyCharacters, setFamilyCharacters] = useState<Character[]>([]);

  useEffect(() => {
    api.fetchCharacters().then(setFamilyCharacters).catch(() => {});
  }, []);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const filesWithPreviews = acceptedFiles.map(file => Object.assign(file, {
        preview: URL.createObjectURL(file)
    }));
    setFiles(prevFiles => [...prevFiles, ...filesWithPreviews]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
    },
    maxSize: 5 * 1024 * 1024,
  });

  useEffect(() => {
    return () => files.forEach(file => URL.revokeObjectURL(file.preview));
  }, [files]);

  const removeFile = (fileName: string) => {
    setFiles(prevFiles => prevFiles.filter(file => file.name !== fileName));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Character name is required.');
      toast.error('Character name is required.');
      return;
    }
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (birthDate && !dateRegex.test(birthDate)) {
        setError('Invalid date format. Please use YYYY-MM-DD.');
        toast.error('Invalid date format.');
        return;
    }

    setLoading(true);
    setUploadingPhotos(false);
    setError(null);

    let createdCharacterId: string | null = null;

    try {
      console.log('Creating character data:', { name, bio, birthdate: birthDate || null });
      const characterPayload = { 
          name: name.trim(), 
          bio: bio.trim(),
          birthdate: birthDate || null 
      };
      const createdCharacter = await api.createCharacter(characterPayload);
      createdCharacterId = createdCharacter.id;
      console.log('Character created successfully:', createdCharacter);
      toast.success(`Character "${createdCharacter.name}" created.`);

      if (files.length > 0 && createdCharacterId) {
        setUploadingPhotos(true);
        console.log(`Uploading ${files.length} photos for character ${createdCharacterId}...`);
        toast.info(`Uploading ${files.length} photo(s)...`);
        
        await api.uploadCharacterPhotos(createdCharacterId, files);
        console.log('Photos uploaded successfully for character:', createdCharacterId);
        toast.success("Photo(s) uploaded successfully!");
        setUploadingPhotos(false);
      }
      
      if (createdCharacterId) {
        navigate(`/characters/${createdCharacterId}`); 
      } else {
          navigate('/characters');
      }

    } catch (err: any) {
      console.error('Error during character creation/photo upload:', err);
      let errorMessage = 'An error occurred.';
      if (uploadingPhotos) {
        errorMessage = 'Failed to upload photos. Please try again later.';
      } else if (createdCharacterId) {
        errorMessage = 'Character created, but failed to upload photos.'; 
        navigate('/characters'); 
      } else {
        errorMessage = 'Failed to create character.';
      }
      
      if (err.response && err.response.data && err.response.data.detail) {
        errorMessage = `${errorMessage} Server response: ${err.response.data.detail}`;
      } else if (err.message) {
        errorMessage = `${errorMessage} Details: ${err.message}`;
      }
      
      setError(errorMessage);
      toast.error(errorMessage);
      setUploadingPhotos(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-4 max-w-2xl">
      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Create New Character</CardTitle>
            <CardDescription>
              Give your character a name, description, and optionally upload photos.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input 
                id="name" 
                placeholder="E.g., Barnaby the Brave Bear" 
                required 
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={loading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="bio">Bio / Description</Label>
              <MentionInput
                value={bio}
                onChange={setBio}
                characters={familyCharacters}
                placeholder="Describe the character... Use @ to mention other characters"
                rows={4}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="birthdate">Birth Date (Optional)</Label>
              <Input 
                id="birthdate" 
                type="date"
                value={birthDate}
                onChange={(e) => setBirthDate(e.target.value)} 
                disabled={loading}
              />
              <p className="text-xs text-muted-foreground">Helps make stories age-appropriate.</p>
            </div>
            <div className="space-y-2">
                <Label htmlFor="photos">Photos (Optional)</Label>
                <div 
                    {...getRootProps()} 
                    className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${isDragActive ? 'border-primary bg-primary/10' : 'border-muted-foreground/50 hover:border-primary/50'}`}
                >
                    <input {...getInputProps()} id="photos" />
                    <UploadIcon className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                    {isDragActive ? (
                        <p>Drop the files here ...</p>
                    ) : (
                        <p>Drag & drop photos here, or click to select files</p>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">PNG, JPG, WEBP up to 5MB each</p>
                </div>
            </div>

            {files.length > 0 && (
                <div className="space-y-2">
                    <Label>Selected Photos:</Label>
                    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
                        {files.map(file => (
                            <div key={file.name} className="relative group aspect-square">
                                <img
                                    src={file.preview}
                                    alt={`Preview ${file.name}`}
                                    className="object-cover w-full h-full rounded-md"
                                    onLoad={() => { URL.revokeObjectURL(file.preview) }}
                                />
                                <Button
                                    variant="destructive"
                                    size="icon"
                                    className="absolute top-1 right-1 h-5 w-5 opacity-75 group-hover:opacity-100 transition-opacity"
                                    onClick={() => removeFile(file.name)}
                                    disabled={loading}
                                >
                                    <Cross1Icon className="h-3 w-3" />
                                    <span className="sr-only">Remove {file.name}</span>
                                </Button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {error && <p className="text-sm text-red-500 dark:text-red-400 pt-2">{error}</p>}
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={loading || uploadingPhotos}>
              {loading ? (uploadingPhotos ? 'Uploading Photos...' : 'Creating Character...') : 'Create Character'}
            </Button>
          </CardFooter>
        </Card>
      </form>
    </div>
  );
} 