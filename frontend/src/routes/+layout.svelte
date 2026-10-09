<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/tracelens-icon.svg';
	import logo from '$lib/assets/tracelens-logo.png';
	import { page } from '$app/state';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>TraceLens — SME Loan Analysis</title>
</svelte:head>

<div class="min-h-screen">
	<header class="workspace-header">
		<div class="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
			<h1 class="brand-logo">
				<img src={logo} alt="TraceLens" width="2720" height="960" />
			</h1>
		</div>
	</header>
	<nav aria-label="Workspace" class="workspace-nav">
		<div class="mx-auto flex max-w-7xl flex-wrap gap-2 px-4 py-3 sm:px-6">
			<a href="/cases" aria-current={page.url.pathname === '/cases' ? 'page' : undefined} class="rounded-lg px-4 py-2 text-sm font-semibold hover:bg-slate-100" class:bg-slate-100={page.url.pathname === '/cases'}>Company cases</a>
			<a href="/" aria-current={page.url.pathname === '/' ? 'page' : undefined} class="rounded-lg px-4 py-2 text-sm font-semibold hover:bg-slate-100" class:bg-slate-100={page.url.pathname === '/'}>Analysis workspace</a>
			<a href="/history" aria-current={page.url.pathname === '/history' ? 'page' : undefined} class="rounded-lg px-4 py-2 text-sm font-semibold hover:bg-slate-100" class:bg-slate-100={page.url.pathname === '/history'}>Development History</a>
		</div>
	</nav>
	<main class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
		{@render children()}
	</main>
</div>
