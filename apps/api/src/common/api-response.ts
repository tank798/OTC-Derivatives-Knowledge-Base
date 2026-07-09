export type ApiResponse<T> =
  | { success: true; data: T }
  | { success: false; error: { message: string; code?: string } };

export function ok<T>(data: T): ApiResponse<T> {
  return { success: true, data };
}

export function fail(message: string, code?: string): ApiResponse<never> {
  return { success: false, error: { message, code } };
}
