export interface LessonRevision {
  id: string;
  revision_number: number;
  short_definition: string;
  caveats: string;
  source_snippet?: string | null;
  reviewer?: string | null;
  created_at: string;
}

export interface LessonReviewEvent {
  action: 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'EDITED';
  reviewer: string;
  reason?: string | null;
  created_at: string;
}

export interface AdminLessonItem {
  id: string;
  title: string;
  source_name: string;
  source_url: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  current_revision?: LessonRevision | null;
  review_events: LessonReviewEvent[];
  created_at?: string;
}

export interface ApprovedLessonItem {
  id: string;
  title: string;
  source_name: string;
  source_url: string;
  revision_id: string;
  revision_number: number;
  short_definition: string;
  caveats: string;
}
