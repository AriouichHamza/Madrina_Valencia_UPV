import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ButtonExamenComponent } from './button-examen.component';

describe('ButtonExamenComponent', () => {
  let component: ButtonExamenComponent;
  let fixture: ComponentFixture<ButtonExamenComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ButtonExamenComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ButtonExamenComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
