import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DeleteExamenComponent } from './delete-examen.component';

describe('DeleteExamenComponent', () => {
  let component: DeleteExamenComponent;
  let fixture: ComponentFixture<DeleteExamenComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DeleteExamenComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DeleteExamenComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
