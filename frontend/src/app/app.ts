import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink, RouterOutlet } from '@angular/router';

interface Version {
  version: number | null;
  commit: string | null;
  fecha: string | null;
}

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  /** «SilVer v12 · abc1234 · 2026-11-20 18:00»: sube con cada PR fusionado. */
  protected version = signal('');

  constructor() {
    inject(HttpClient)
      .get<Version>('/api/version')
      .subscribe({
        next: (v) =>
          this.version.set(
            v.version ? `SilVer v${v.version} · ${v.commit} · ${v.fecha}` : 'SilVer versión desconocida',
          ),
        error: () => this.version.set(''),
      });
  }
}
