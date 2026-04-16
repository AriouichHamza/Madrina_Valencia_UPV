import { TestBed } from '@angular/core/testing';

import { AuthorizedGuardGuard } from './authorized-guard.guard';

describe('AuthorizedGuardGuard', () => {
  let guard: AuthorizedGuardGuard;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    guard = TestBed.inject(AuthorizedGuardGuard);
  });

  it('should be created', () => {
    expect(guard).toBeTruthy();
  });
});
