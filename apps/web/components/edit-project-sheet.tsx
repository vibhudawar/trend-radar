"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";

import { deleteProjectAction, updateProjectAction } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const REGIONS = ["US", "IN", "UK", "CA", "AU", "Global"];

export type EditableProject = {
  id: string;
  name: string;
  jobToBeDone: string | null;
  productDescription: string | null;
  audience: string | null;
  productUrl: string | null;
  region: string | null;
};

// Edit the business details captured at onboarding, from a slide-over next to the project title.
export function EditProjectSheet({ project }: { project: EditableProject }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [pending, start] = useTransition();

  function onDelete() {
    setError(null);
    start(async () => {
      await deleteProjectAction(project.id); // redirects to "/" on success
    });
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setError(null);
    start(async () => {
      const r = await updateProjectAction(project.id, fd);
      if (r.ok) {
        setOpen(false);
        router.refresh();
      } else {
        setError(r.error ?? "Could not save changes");
      }
    });
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={<Button variant="ghost" size="icon-sm" aria-label="Edit details" title="Edit details" />}
      >
        <Pencil className="size-4" />
      </SheetTrigger>
      <SheetContent side="right" className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="border-b">
          <SheetTitle>Edit details</SheetTitle>
          <SheetDescription>
            These drive discovery and how winning ideas get adapted for you.
          </SheetDescription>
        </SheetHeader>

        <form onSubmit={onSubmit} className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            <Row label="Business name">
              <Input name="name" defaultValue={project.name} required />
            </Row>
            <Row label="Goal" hint="The job to be done — what you want to achieve.">
              <Textarea name="jobToBeDone" rows={3} defaultValue={project.jobToBeDone ?? ""} />
            </Row>
            <Row label="About" hint="What the product/service is.">
              <Textarea name="productDescription" rows={4} defaultValue={project.productDescription ?? ""} />
            </Row>
            <Row label="Audience">
              <Textarea name="audience" rows={3} defaultValue={project.audience ?? ""} />
            </Row>
            <Row label="Website">
              <Input name="productUrl" type="url" defaultValue={project.productUrl ?? ""} placeholder="https://…" />
            </Row>
            <Row label="Region">
              <select
                name="region"
                defaultValue={project.region ?? ""}
                className={cn(
                  "border-input bg-transparent flex h-9 w-full rounded-md border px-3 text-sm shadow-xs",
                  "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                )}
              >
                {REGIONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
                {project.region && !REGIONS.includes(project.region) ? (
                  <option value={project.region}>{project.region}</option>
                ) : null}
              </select>
            </Row>

            {error ? <p className="text-sm text-red-500">{error}</p> : null}

            <div className="mt-2 border-t pt-4">
              {confirmDelete ? (
                <div className="border-destructive/30 bg-destructive/5 flex flex-col gap-2.5 rounded-md border p-3">
                  <p className="text-sm">Delete this project? Its concepts, sounds, and history stop showing. This can&apos;t be undone from the UI.</p>
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmDelete(false)} disabled={pending}>
                      Cancel
                    </Button>
                    <Button type="button" variant="destructive" size="sm" onClick={onDelete} disabled={pending}>
                      {pending ? "Deleting…" : "Delete project"}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmDelete(true)}
                  className="text-destructive hover:text-destructive hover:bg-destructive/10 gap-2"
                >
                  <Trash2 className="size-4" />
                  Delete project
                </Button>
              )}
            </div>
          </div>

          <SheetFooter className="flex-row justify-end border-t">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={pending}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? "Saving…" : "Save changes"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium">{label}</Label>
      {children}
      {hint ? <p className="text-muted-foreground text-xs">{hint}</p> : null}
    </div>
  );
}
