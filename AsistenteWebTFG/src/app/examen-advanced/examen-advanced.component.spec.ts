import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ExamenAdvancedComponent } from './examen-advanced.component';

describe('ExamenComponent', () => {
  let component: ExamenAdvancedComponent;
  let fixture: ComponentFixture<ExamenAdvancedComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ExamenAdvancedComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ExamenAdvancedComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
