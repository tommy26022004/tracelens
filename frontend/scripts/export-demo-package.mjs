import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createServer } from 'vite';

const outputDirectory = resolve(process.argv[2] ?? '../tmp/demo-package');
await mkdir(outputDirectory, { recursive: true });

const server = await createServer({
    root: resolve(import.meta.dirname, '..'),
    appType: 'custom',
    server: { middlewareMode: true }
});

try {
    const { createDemoPackage } = await server.ssrLoadModule('/src/lib/demoPackage.ts');
    for (const file of createDemoPackage()) {
        await writeFile(resolve(outputDirectory, file.name), Buffer.from(await file.arrayBuffer()));
    }
} finally {
    await server.close();
}
