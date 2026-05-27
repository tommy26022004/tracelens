<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>FYP — SME Loan Risk Analyser</title>
</svelte:head>

<div class="min-h-screen">
	<header class="border-b border-slate-200 bg-white">
		<div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
			<div>
				<h1 class="text-lg font-semibold text-slate-900">SME Loan Risk Analyser</h1>
				<p class="text-xs text-slate-500">Agentic AI · BNM FEATERS-aligned · APU FYP</p>
			</div>
			<span
				class="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200"
				>Prototype</span
			>
		</div>
	</header>
	<main class="mx-auto max-w-6xl px-6 py-8">
		{@render children()}
	</main>
</div>
