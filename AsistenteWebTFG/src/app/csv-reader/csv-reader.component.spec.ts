import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CsvReaderComponent } from './csv-reader.component';

describe('CsvReaderComponent', () => {
  let component: CsvReaderComponent;
  let fixture: ComponentFixture<CsvReaderComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CsvReaderComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(CsvReaderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
