; IDL Script to generate Tsunakawa 2015 SVM Magnetic Anomaly Grid
; Requires SPEDAS/TDAS to be installed and loaded

PRO generate_svm_grid
  compile_opt idl2
  
  res = 0.5 ; Resolution in degrees (change to 0.25 for higher res)
  nlon = long(360.0 / res)
  nlat = long(180.0 / res)
  r_moon = 1737.4 ; km

  print, "Generating coordinate grid..."
  ; Create arrays for cell centers
  lon = findgen(nlon) * res - 180.0 + (res/2.0)
  lat = (findgen(nlat) * res - 90.0 + (res/2.0)) * -1.0 ; start from 90 (North) down to -90 (South) for standard TIFF orientation
  
  ; Create 3xN rvec
  n_points = nlon * nlat
  rvec = dblarr(3, n_points)

  idx = 0L
  for j=0L, nlat-1 do begin
    for i=0L, nlon-1 do begin
      theta = (90.0 - lat[j]) * !dtor ; colatitude
      phi = lon[i] * !dtor
      rvec[0, idx] = r_moon * sin(theta) * cos(phi)
      rvec[1, idx] = r_moon * sin(theta) * sin(phi)
      rvec[2, idx] = r_moon * cos(theta)
      idx++
    endfor
  endfor

  print, "Loading SVM data (this may download data from the internet)..."
  kgy_svm_load

  print, "Calculating B-field vectors from SVM..."
  bvec = kgy_svm_get(rvec)

  print, "Calculating magnitudes..."
  bmag = sqrt(bvec[0,*]^2 + bvec[1,*]^2 + bvec[2,*]^2)

  ; Reshape into 2D grid
  bmag_grid = reform(bmag, nlon, nlat)

  print, "Writing to magnetic_anomaly_grid.csv..."
  openw, 1, 'magnetic_anomaly_grid.csv'
  for j=0L, nlat-1 do begin
    printf, 1, strjoin(strtrim(bmag_grid[*, j], 2), ',')
  endfor
  close, 1
  
  print, "Done! Saved to magnetic_anomaly_grid.csv"
END
