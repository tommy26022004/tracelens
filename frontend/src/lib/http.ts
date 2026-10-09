const apiBaseUrl = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') ?? '';

export function apiUrl(path: string): string {
	if (!path.startsWith('/')) {
		throw new Error(`API path must start with /: ${path}`);
	}
	return `${apiBaseUrl}${path}`;
}
