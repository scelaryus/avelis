import { NavLink, useLocation } from 'react-router-dom';
import { useMemo } from 'react';
import { useStore } from '../../store/useStore';
import { getActiveModuleByPath, getVisibleModules } from './navigationConfig';

export function TopSubnav() {
  const location = useLocation();
  const userModules = useStore((state) => state.user?.modules || []);
  const visibleModules = useMemo(() => getVisibleModules(userModules), [userModules]);
  const activeModule = useMemo(
    () => getActiveModuleByPath(location.pathname, visibleModules),
    [location.pathname, visibleModules]
  );

  if (!activeModule) return null;

  return (
    <div className="border-b border-rose-200/70 bg-gradient-to-r from-rose-50 via-red-50 to-rose-100">
      <div className="mx-auto flex max-w-7xl items-center gap-2 overflow-x-auto px-6 py-3">
        <span className="shrink-0 rounded-full bg-rose-800 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-white shadow-sm">
          {activeModule.label}
        </span>
        {activeModule.items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `whitespace-nowrap rounded-full border px-3 py-1.5 text-sm transition ${
                isActive
                  ? 'border-rose-700 bg-rose-800 text-white shadow-sm'
                  : 'border-transparent bg-white/80 text-slate-700 hover:border-rose-300 hover:bg-white'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}
