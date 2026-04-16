import { ComponentFixture, TestBed } from '@angular/core/testing';

import { EditAsignaturaComponent } from './edit-asignatura.component';

describe('EditAsignaturaComponent', () => {
  let component: EditAsignaturaComponent;
  let fixture: ComponentFixture<EditAsignaturaComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ EditAsignaturaComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(EditAsignaturaComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
