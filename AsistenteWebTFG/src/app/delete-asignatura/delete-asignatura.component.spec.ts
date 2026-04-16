import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DeleteAsignaturaComponent } from './delete-asignatura.component';

describe('DeleteAsignaturaComponent', () => {
  let component: DeleteAsignaturaComponent;
  let fixture: ComponentFixture<DeleteAsignaturaComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DeleteAsignaturaComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DeleteAsignaturaComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
