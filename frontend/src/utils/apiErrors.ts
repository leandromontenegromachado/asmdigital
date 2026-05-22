export const formatApiError = (detail: any, fallback: string): string => {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => formatApiError(item, '')).filter(Boolean).join('\n');
  }

  const lines: string[] = [];
  if (typeof detail.message === 'string') {
    lines.push(detail.message);
  }

  const issues = Array.isArray(detail.possible_issues) ? detail.possible_issues : [];
  if (issues.length) {
    lines.push('', 'Pontos que podem estar ambíguos:');
    issues.slice(0, 5).forEach((item: any) => lines.push(`- ${String(item)}`));
  }

  const identified = detail.identified && typeof detail.identified === 'object' ? detail.identified : null;
  if (identified) {
    const parts: string[] = [];
    if (Array.isArray(identified.project_ids) && identified.project_ids.length) {
      parts.push(`projeto: ${identified.project_ids.join(', ')}`);
    }
    if (identified.status_scope) {
      parts.push(`escopo de status: ${identified.status_scope}`);
    }
    if (Array.isArray(identified.columns) && identified.columns.length) {
      parts.push(`colunas detectadas: ${identified.columns.length}`);
    }
    if (Array.isArray(identified.filters) && identified.filters.length) {
      parts.push(`filtros detectados: ${identified.filters.length}`);
    }
    if (parts.length) {
      lines.push('', `O que consegui identificar: ${parts.join('; ')}.`);
    }
  }

  const suggestions = Array.isArray(detail.suggestions) ? detail.suggestions : [];
  if (suggestions.length) {
    lines.push('', 'Como corrigir:');
    suggestions.slice(0, 5).forEach((item: any) => lines.push(`- ${String(item)}`));
  }

  if (typeof detail.ai_error === 'string' && detail.ai_error) {
    const compact = detail.ai_error.split('\n')[0];
    lines.push('', `Erro técnico: ${compact}`);
  }

  if (lines.length) return lines.join('\n');

  try {
    return JSON.stringify(detail, null, 2);
  } catch {
    return fallback;
  }
};
