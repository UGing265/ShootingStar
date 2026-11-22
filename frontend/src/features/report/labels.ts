import type { ExternalAnalysisStatus } from '../replay/external-types';

export const IN_PROGRESS_STATUSES: readonly ExternalAnalysisStatus[] = [
  'PREPARING',
  'PREPARING_FEED',
  'ANALYZING',
  'RESEARCHING',
  'MATCHING',
  'SYNTHESIZING',
  'CALLING',
];

/** Ordered pipeline stages shown while a report is being written. */
export const PIPELINE_STEPS: ReadonlyArray<{ status: ExternalAnalysisStatus; label: string }> = [
  { status: 'PREPARING_FEED', label: 'Chuẩn bị 6 giờ nến' },
  { status: 'ANALYZING', label: 'Lập giả thuyết' },
  { status: 'RESEARCHING', label: 'Tra cứu tài liệu' },
  { status: 'MATCHING', label: 'Đối chiếu tiêu chí' },
  { status: 'SYNTHESIZING', label: 'Viết báo cáo' },
];

const STATUS_LABELS: Record<ExternalAnalysisStatus, string> = {
  PREPARING: 'Đang chuẩn bị',
  PREPARING_FEED: 'Đang chuẩn bị 6 giờ nến',
  ANALYZING: 'Đang lập giả thuyết',
  RESEARCHING: 'Đang tra cứu tài liệu',
  MATCHING: 'Đang đối chiếu tiêu chí',
  SYNTHESIZING: 'Đang viết báo cáo',
  CALLING: 'Đang gọi mô hình',
  READY: 'Hoàn tất',
  ABSTAIN: 'Không đủ căn cứ để dự báo',
  RESEARCH_INCOMPLETE: 'Tra cứu chưa đầy đủ',
  FAILED: 'Thất bại',
  FAILED_INTERRUPTED: 'Bị gián đoạn',
  INSUFFICIENT_HISTORY: 'Thiếu lịch sử nến',
  UNSCORABLE: 'Không chấm điểm được',
};

export function externalStatusLabel(status: ExternalAnalysisStatus): string {
  return STATUS_LABELS[status];
}

export function isInProgress(status: ExternalAnalysisStatus): boolean {
  return IN_PROGRESS_STATUSES.includes(status);
}

export type BadgeVariant = 'success' | 'warning' | 'error' | 'neutral' | 'accent';

export function statusVariant(status: ExternalAnalysisStatus): BadgeVariant {
  if (status === 'READY') return 'success';
  if (status === 'FAILED' || status === 'FAILED_INTERRUPTED') return 'error';
  if (isInProgress(status)) return 'accent';
  return 'warning';
}

export function outcomeLabel(outcome: string | null | undefined): string {
  switch (outcome) {
    case 'UP':
      return 'Tăng';
    case 'DOWN':
      return 'Giảm';
    case 'FLAT':
      return 'Đi ngang';
    case 'PENDING':
      return 'Chờ kết quả';
    case 'UNSCORABLE':
      return 'Không chấm điểm được';
    default:
      return 'Chưa có dữ liệu';
  }
}

export function matchLabel(status: string): string {
  switch (status) {
    case 'KHỚP_THEO_RULE_VERSION':
      return 'Khớp quy tắc';
    case 'KHÔNG_KHỚP':
      return 'Không khớp';
    case 'CHƯA_ĐỦ_TIÊU_CHÍ':
      return 'Chưa đủ tiêu chí';
    default:
      return status;
  }
}

export function criterionLabel(status: 'PASS' | 'FAIL' | 'UNKNOWN'): string {
  return status === 'PASS' ? 'Đạt' : status === 'FAIL' ? 'Không đạt' : 'Chưa rõ';
}
