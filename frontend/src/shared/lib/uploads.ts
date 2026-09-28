import { toPersianDigits } from "@/shared/lib/persian";
import type { UploadLimit } from "@/types/domain";

/** A limit in whole megabytes, in Persian digits. */
export function megabytes(bytes: number): string {
  return toPersianDigits(Math.round(bytes / (1024 * 1024)));
}

/** «JPEG، PNG یا WebP تا ۱۰ مگابایت» */
export function describeUpload(limit: UploadLimit): string {
  return `${limit.formats} تا ${megabytes(limit.max_bytes)} مگابایت`;
}

/**
 * Why a file would be refused, in the words the server itself would use --
 * or null if it may be sent. Checked first so a large or wrong file is not
 * uploaded only to be turned away; the server checks again regardless.
 */
export function checkUpload(
  file: File,
  limit: UploadLimit | undefined,
  label: string,
): string | null {
  if (!limit) return null;

  if (limit.types && !limit.types.includes(file.type)) {
    return `فقط ${label} با فرمت ${limit.formats} پذیرفته می‌شود.`;
  }
  if (file.size > limit.max_bytes) {
    return `حجم ${label} نباید از ${megabytes(limit.max_bytes)} مگابایت بیشتر باشد.`;
  }
  return null;
}
