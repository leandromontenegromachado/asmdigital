interface TableColumn<T> {
  key: keyof T;
  label: string;
  className?: string;
}

interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  emptyMessage?: string;
}

export function Table<T extends Record<string, any>>({ columns, data, emptyMessage }: TableProps<T>) {
  if (!data.length) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
        {emptyMessage || 'Sem dados para exibir.'}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            {columns.map((column) => (
              <th key={String(column.key)} className={`px-4 py-3 text-left font-semibold ${column.className || ''}`}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr key={idx} className="border-t border-slate-100">
              {columns.map((column) => (
                <td key={String(column.key)} className={`px-4 py-3 text-slate-700 ${column.className || ''}`}>
                  {row[column.key] ?? '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
