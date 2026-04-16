import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ButtonAsignaturaComponent } from './button-asignatura.component';

describe('ButtonAsignaturaComponent', () => {
  let component: ButtonAsignaturaComponent;
  let fixture: ComponentFixture<ButtonAsignaturaComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ButtonAsignaturaComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ButtonAsignaturaComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
