export const MAX_PACKAGE_FILES = 50;
export const MAX_PACKAGE_BYTES = 100 * 1024 * 1024;

export function validatePackage(files: readonly { name: string; size: number }[]): string | null {
    if (files.length === 0) return 'Add at least one PDF before analysis.';
    if (files.length > MAX_PACKAGE_FILES) return `A package can contain at most ${MAX_PACKAGE_FILES} PDFs.`;
    if (files.some((file) => !file.name.toLowerCase().endsWith('.pdf'))) return 'Only PDF documents are supported.';
    if (files.some((file) => file.size === 0)) return 'Remove empty files before analysis.';
    if (files.reduce((total, file) => total + file.size, 0) > MAX_PACKAGE_BYTES) {
        return 'The package exceeds the 100 MB limit. Remove files before analysis.';
    }
    return null;
}
