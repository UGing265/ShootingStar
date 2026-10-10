import 'server-only';
/**
 * Server-only HTTP API Client for ShootingStar Backend (FastAPI).
 * Invariant: Never executes client-side; never leaks backend credentials.
 */


export interface ApiResult<T> {
  data: T | null;
  error: string | null;
  status: number;
}

export async function fetchFromApi<T>(
  path: string,
  params?: Record<string, string | number | undefined | null>,
  customHeaders?: Record<string, string>
): Promise<ApiResult<T>> {
  const baseUrl = process.env.SHOOTINGSTAR_API_URL || 'http://127.0.0.1:8000';
  const url = new URL(path.startsWith('/') ? path : `/${path}`, baseUrl);

  if (params) {
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        url.searchParams.set(key, String(val));
      }
    });
  }

  try {
    const res = await fetch(url.toString(), {
      cache: 'no-store',
      headers: {
        'Accept': 'application/json',
        ...customHeaders,
      },
    });

    if (!res.ok) {
      let errorMsg = `API responded with HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body.detail) {
          errorMsg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        }
      } catch {
        // Fallback to HTTP status text
      }
      return { data: null, error: errorMsg, status: res.status };
    }

    const data = (await res.json()) as T;
    return { data, error: null, status: res.status };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to connect to backend';
    return { data: null, error: message, status: 503 };
  }
}

export async function postToApi<T>(
  path: string,
  body: unknown,
  customHeaders?: Record<string, string>
): Promise<ApiResult<T>> {
  const baseUrl = process.env.SHOOTINGSTAR_API_URL || 'http://127.0.0.1:8000';
  const url = new URL(path.startsWith('/') ? path : `/${path}`, baseUrl);

  try {
    const res = await fetch(url.toString(), {
      method: 'POST',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...customHeaders,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      let errorMsg = `API responded with HTTP ${res.status}`;
      try {
        const errBody = await res.json();
        if (errBody.detail) {
          errorMsg = typeof errBody.detail === 'string' ? errBody.detail : JSON.stringify(errBody.detail);
        }
      } catch {
        // Fallback
      }
      return { data: null, error: errorMsg, status: res.status };
    }

    const data = (await res.json()) as T;
    return { data, error: null, status: res.status };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to connect to backend';
    return { data: null, error: message, status: 503 };
  }
}
