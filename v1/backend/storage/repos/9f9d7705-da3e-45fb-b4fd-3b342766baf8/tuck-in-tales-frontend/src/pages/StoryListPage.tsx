import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { toast } from 'sonner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge" // For status
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Hourglass, CheckCircle, XCircle, Eye, Play, Trash2 } from "lucide-react" // Icons + Trash2
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ExclamationTriangleIcon } from "@radix-ui/react-icons"
import type { StoryBasic } from '@/models/story'; // Assuming StoryBasic is in models/story
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

export default function StoryListPage() {
  const [stories, setStories] = useState<StoryBasic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadStories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listStories();
      setStories(data);
    } catch (err: any) {
      console.error("Error fetching stories:", err);
      setError(err.message || 'Failed to load stories.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStories();
  }, [loadStories]);

  const handleStoryClick = (story: StoryBasic) => {
    console.log(`Handling click for story ID: ${story.id}, Status: '${story.status}'`); // Log status
    if (story.status === 'COMPLETED') {
      const destination = `/stories/${story.id}/view`;
      console.log(`Status is COMPLETED, navigating to: ${destination}`); // Log destination
      navigate(destination); // Navigate to viewer for completed
    } else {
      const destination = `/stories/${story.id}`;
      console.log(`Status is NOT COMPLETED ('${story.status}'), navigating to: ${destination}`); // Log destination
      navigate(destination); // Navigate to progress page otherwise
    }
  };

  const handleDeleteConfirm = async (storyId: string) => {
    console.log(`Attempting to delete story: ${storyId}`);
    try {
      await api.deleteStory(storyId);
      setStories(prevStories => prevStories.filter(story => story.id !== storyId));
      toast.success("Story deleted successfully!");
    } catch (err: any) {
      console.error("Error deleting story:", err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to delete story.';
      toast.error(`Error: ${errorMsg}`);
    }
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <Badge variant="default"><CheckCircle className="mr-1 h-3 w-3" /> Completed</Badge>;
      case 'FAILED':
        return <Badge variant="destructive"><XCircle className="mr-1 h-3 w-3" /> Failed</Badge>;
      case 'GENERATING_PAGES':
      case 'OUTLINING':
      case 'INITIALIZING':
        return <Badge variant="secondary"><Hourglass className="mr-1 h-3 w-3 animate-spin" /> In Progress</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="container mx-auto p-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>My Stories</CardTitle>
            <CardDescription>View generated stories or track their progress.</CardDescription>
          </div>
          <Button onClick={() => navigate('/stories/generate')}>
             Generate New Story
          </Button>
        </CardHeader>
        <CardContent>
          {loading && (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}
          {error && (
            <Alert variant="destructive">
              <ExclamationTriangleIcon className="h-4 w-4" />
              <AlertTitle>Error Loading Stories</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {!loading && !error && stories.length === 0 && (
            <p className="text-center text-muted-foreground py-4">No stories generated yet.</p>
          )}
          {!loading && !error && stories.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stories.map((story) => (
                  <TableRow key={story.id} className="cursor-pointer hover:bg-muted/50" onClick={() => handleStoryClick(story)}>
                    <TableCell className="font-medium">{story.title || "Untitled Story"}</TableCell>
                    <TableCell>{renderStatusBadge(story.status)}</TableCell>
                    <TableCell>{new Date(story.created_at).toLocaleDateString()}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm">
                        {story.status === 'COMPLETED' ? <Eye className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                        <span className="sr-only">{story.status === 'COMPLETED' ? 'View' : 'Track Progress'}</span>
                      </Button>
                      {/* Delete Button with Confirmation */}
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button 
                             variant="ghost" 
                             size="sm" 
                             className="text-destructive hover:text-destructive"
                             onClick={(e) => e.stopPropagation()} // Prevent row click
                           >
                             <Trash2 className="h-4 w-4" />
                            <span className="sr-only">Delete</span>
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This action cannot be undone. This will permanently delete the story
                              "<strong>{story.title || 'Untitled Story'}</strong>" and its associated images.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel onClick={(e) => e.stopPropagation()}>Cancel</AlertDialogCancel>
                            <AlertDialogAction 
                               className="bg-destructive hover:bg-destructive/90"
                              onClick={(e) => {
                                e.stopPropagation(); // Prevent row click
                                handleDeleteConfirm(story.id);
                              }}
                             >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
} 