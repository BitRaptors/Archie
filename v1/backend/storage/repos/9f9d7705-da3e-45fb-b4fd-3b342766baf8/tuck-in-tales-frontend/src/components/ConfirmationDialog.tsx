import React from 'react';
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
} from "@/components/ui/alert-dialog";
import { Button, ButtonProps } from "@/components/ui/button";

interface ConfirmationDialogProps {
  triggerButton: React.ReactNode;
  title: string;
  description: string;
  confirmAction: () => void;
  confirmButtonText?: string;
  confirmButtonVariant?: ButtonProps['variant']; // Allow passing variant
}

export function ConfirmationDialog({
  triggerButton,
  title,
  description,
  confirmAction,
  confirmButtonText = "Confirm",
  confirmButtonVariant = "destructive", // Default to destructive for deletes
}: ConfirmationDialogProps) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        {triggerButton}
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={confirmAction} className={confirmButtonVariant === "destructive" ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : ""}>
            {confirmButtonText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
} 