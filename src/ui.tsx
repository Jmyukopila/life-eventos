import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { ArrowUpRight, X, LoaderCircle } from 'lucide-react';

export function Brand({ light = false }: { light?: boolean }) {
  return <a className={`brand ${light ? 'brand-light' : ''}`} href="#/" aria-label="Life, inicio"><svg viewBox="0 0 42 48" aria-hidden="true"><path d="M23 4c10-2 15 6 10 14-4 7-14 8-16 16l-2 10C9 37 9 30 15 23c6-6 10-7 8-13Z" fill="currentColor"/><path d="M8 18c7-1 10 4 6 10L5 40C0 32 1 24 8 18Z" fill="currentColor" opacity=".7"/></svg><span className="brand-word">life<span className="brand-dot">.</span></span><span className="brand-tag">Una casa para<br/>las naciones</span></a>;
}
export function Loading({ label = 'Cargando…' }: { label?: string }) {
  // El plan gratuito del servidor se duerme sin tráfico. Si la espera se alarga, decirlo evita
  // que parezca una página rota: la gente aguanta un minuto si sabe por qué.
  const [lento, setLento] = useState(false);
  useEffect(() => {
    const aviso = setTimeout(() => setLento(true), 4000);
    return () => clearTimeout(aviso);
  }, []);
  return <div className="loading" role="status"><LoaderCircle className="spin" size={22}/><span>{label}</span>{lento && <span className="loading-lento">El servidor estaba en reposo y está despertando. La primera carga puede tardar hasta un minuto.</span>}</div>;
}
export function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="error-notice" role="alert"><p>{message}</p>{retry && <button className="button secondary" onClick={retry}>Volver a intentar</button>}</div>;
}
export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { dialog?.close(); document.body.style.overflow = overflow; previous?.focus(); };
  }, []);
  return <dialog ref={ref} className={`modal ${wide ? 'modal-wide' : ''}`} aria-label={title} onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => { if (event.target === ref.current) onClose(); }}><div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Cerrar"><X size={22}/></button></div>{children}</dialog>;
}
export const Arrow = () => <ArrowUpRight size={19} aria-hidden="true"/>;
export function formatDate(value: string, options?: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat('es-CO', { timeZone: 'America/Bogota', day: 'numeric', month: 'long', ...options }).format(new Date(value));
}
export function formatTime(value: string) {
  return new Intl.DateTimeFormat('es-CO', { timeZone: 'America/Bogota', hour: 'numeric', minute: '2-digit' }).format(new Date(value));
}
