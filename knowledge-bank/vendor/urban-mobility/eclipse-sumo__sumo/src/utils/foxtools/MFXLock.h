/****************************************************************************/
// Eclipse SUMO, Simulation of Urban MObility; see https://eclipse.dev/sumo
// Copyright (C) 2004-2026 German Aerospace Center (DLR) and others.
// This program and the accompanying materials are made available under the
// terms of the Eclipse Public License 2.0 which is available at
// https://www.eclipse.org/legal/epl-2.0/
// This Source Code may also be made available under the following Secondary
// Licenses when the conditions for such availability set forth in the Eclipse
// Public License 2.0 are satisfied: GNU General Public License, version 2
// or later which is available at
// https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
// SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later
/****************************************************************************/
/// @file    MFXLock.h
/// @author  Jakob Erdmann
/// @date    2026-02-10
///
// A derived class from MFXOptionalLock that does locking
/****************************************************************************/
#pragma once
#include <config.h>
#include "MFXOptionalLock.h"

#ifdef HAVE_FOX
#include "fxheader.h"
#endif

class MFXLock : public MFXOptionalLock {
public:
    explicit MFXLock(FXMutex& lock): myMutexLock(lock) {}

private:
    FXMutexLock myMutexLock;
};
