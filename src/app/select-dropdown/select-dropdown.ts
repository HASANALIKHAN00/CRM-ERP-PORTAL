import { Component, Input, Output, EventEmitter, ElementRef, ViewChild, ChangeDetectorRef, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-select-dropdown',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './select-dropdown.html',
  styleUrl: './select-dropdown.scss'
})
export class SelectDropdownComponent {
  @Input() options: string[] = [];
  @Input() value = '';
  @Output() valueChange = new EventEmitter<string>();

  @ViewChild('trigger') triggerRef?: ElementRef<HTMLButtonElement>;

  isOpen = false;
  dropdownTop = 0;
  dropdownLeft = 0;
  dropdownWidth = 0;

  constructor(private cdr: ChangeDetectorRef, private hostRef: ElementRef) {}

  toggle(): void {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  private open(): void {
    const el = this.triggerRef?.nativeElement;
    if (el) {
      const rect = el.getBoundingClientRect();
      this.dropdownTop = rect.bottom + 4;
      this.dropdownLeft = rect.left;
      this.dropdownWidth = rect.width;
    }
    this.isOpen = true;
    this.cdr.detectChanges();
  }

  close(): void {
    this.isOpen = false;
    this.cdr.detectChanges();
  }

  select(opt: string): void {
    this.value = opt;
    this.valueChange.emit(opt);
    this.close();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.isOpen && !this.hostRef.nativeElement.contains(event.target as Node)) {
      this.close();
    }
  }
}