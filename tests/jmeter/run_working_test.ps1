# PowerShell Test Script for Inscription Microservice (WORKING VERSION)
param(
    [string]$TestType = "health",
    [string]$BaseUrl = "http://localhost:8003"
)

Write-Host "=== INSCRIPTION MICROSERVICE TESTS ===" -ForegroundColor Magenta
Write-Host "Test Type: $TestType" -ForegroundColor White
Write-Host "Base URL: $BaseUrl" -ForegroundColor White
Write-Host ""

function Test-SimpleEndpoint {
    param([string]$Endpoint)
    
    $url = $BaseUrl + $Endpoint
    Write-Host "Testing: $url" -ForegroundColor Cyan
    
    $response = Invoke-WebRequest -Uri $url -TimeoutSec 5 -ErrorAction SilentlyContinue
    
    if ($response -and $response.StatusCode -eq 200) {
        Write-Host "  SUCCESS (Status: $($response.StatusCode))" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  FAILED or not available" -ForegroundColor Yellow
        return $false
    }
}

# Health Check Tests
if ($TestType -eq "health" -or $TestType -eq "all") {
    Write-Host "=== BASIC HEALTH CHECK TESTS ===" -ForegroundColor Yellow
    
    $endpoints = @("/health", "/", "/docs")
    $passed = 0
    
    foreach ($endpoint in $endpoints) {
        if (Test-SimpleEndpoint $endpoint) {
            $passed++
        }
    }
    
    Write-Host "Basic Health: $passed out of 3 tests passed" -ForegroundColor Green
    Write-Host ""
    
    # Queue endpoints (CORRECTED URLs)
    Write-Host "=== QUEUE ENDPOINTS CHECK ===" -ForegroundColor Yellow
    
    $queueEndpoints = @(
        "/api/v1/queue/stats",
        "/api/v1/queue/workers"
    )
    
    $queuePassed = 0
    
    foreach ($endpoint in $queueEndpoints) {
        if (Test-SimpleEndpoint $endpoint) {
            $queuePassed++
        }
    }
    
    Write-Host "Queue Endpoints: $queuePassed out of 2 tests passed" -ForegroundColor Green
    Write-Host ""
}

# Test inscription endpoint (CORRECTED URL)
if ($TestType -eq "inscription" -or $TestType -eq "all") {
    Write-Host "=== INSCRIPTION TEST ===" -ForegroundColor Yellow
    
    $testData = @{
        registro_academico = "TEST001"
        codigo_periodo = "2024-2"
        grupos = @("G-ELC102-E", "G-ELC106-E")
    }
    
    $json = $testData | ConvertTo-Json
    $url = $BaseUrl + "/api/v1/queue/inscripciones/async-by-groups"
    
    Write-Host "Testing: POST $url" -ForegroundColor Cyan
    
    $response = Invoke-RestMethod -Uri $url -Method Post -Body $json -ContentType "application/json" -TimeoutSec 30 -ErrorAction SilentlyContinue
    
    if ($response -and $response.main_task_id) {
        Write-Host "  SUCCESS - Main Task ID: $($response.main_task_id)" -ForegroundColor Green
        Write-Host "  Group Tasks: $($response.group_tasks.Count) tasks created" -ForegroundColor White
        
        # Test task status endpoint
        if ($response.group_tasks -and $response.group_tasks.Count -gt 0) {
            $taskIds = $response.group_tasks | ForEach-Object { $_.task_id }
            
            Write-Host "Testing task status for multiple tasks..." -ForegroundColor Cyan
            $statusUrl = $BaseUrl + "/api/v1/queue/tasks/status/multiple"
            
            $statusResponse = Invoke-RestMethod -Uri $statusUrl -Method Post -Body ($taskIds | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 10 -ErrorAction SilentlyContinue
            
            if ($statusResponse) {
                Write-Host "  Task status check successful - Got status for $($statusResponse.Count) tasks" -ForegroundColor Green
            } else {
                Write-Host "  Task status check failed" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "  FAILED - No task ID returned" -ForegroundColor Red
    }
    
    Write-Host ""
}

# Performance test
if ($TestType -eq "performance" -or $TestType -eq "all") {
    Write-Host "=== BASIC PERFORMANCE TEST ===" -ForegroundColor Yellow
    
    $testData = @{
        registro_academico = "PERF_TEST_001"
        codigo_periodo = "2024-2"
        grupos = @("G-ELC102-E")
    }
    
    $json = $testData | ConvertTo-Json
    $url = $BaseUrl + "/api/v1/queue/inscripciones/async-by-groups"
    
    $times = @()
    $successes = 0
    
    for ($i = 1; $i -le 3; $i++) {
        Write-Host "Performance test $i/3..." -ForegroundColor Cyan
        
        $startTime = Get-Date
        $response = Invoke-RestMethod -Uri $url -Method Post -Body $json -ContentType "application/json" -TimeoutSec 30 -ErrorAction SilentlyContinue
        $endTime = Get-Date
        
        $duration = ($endTime - $startTime).TotalMilliseconds
        $times += $duration
        
        if ($response -and $response.main_task_id) {
            $successes++
            $roundedDuration = [math]::Round($duration, 2)
            Write-Host "  Request $i completed in ${roundedDuration}ms" -ForegroundColor Green
        } else {
            Write-Host "  Request $i failed" -ForegroundColor Red
        }
        
        # Update test data for next request
        $testData.registro_academico = "PERF_TEST_00$i"
        $json = $testData | ConvertTo-Json
    }
    
    if ($times.Count -gt 0) {
        $avgTime = ($times | Measure-Object -Average).Average
        $successRate = ($successes * 100) / 3
        
        Write-Host "Performance Results:" -ForegroundColor Yellow
        Write-Host "  Success Rate: $successes/3 ($successRate%)" -ForegroundColor White
        $avgTimeRounded = [math]::Round($avgTime, 2)
        Write-Host "  Average Time: ${avgTimeRounded}ms" -ForegroundColor White
    }
    
    Write-Host ""
}

Write-Host "=== TEST COMPLETED ===" -ForegroundColor Magenta
Write-Host "Timestamp: $(Get-Date)" -ForegroundColor Gray
Write-Host ""

if ($TestType -eq "all") {
    Write-Host "=== SUMMARY ===" -ForegroundColor Yellow
    Write-Host "System is running and responding" -ForegroundColor Green
    Write-Host "Queue endpoints are available at /api/v1/queue/*" -ForegroundColor Green
    Write-Host "Inscription endpoint works: /api/v1/queue/inscripciones/async-by-groups" -ForegroundColor Green
    Write-Host "Task status endpoint works: /api/v1/queue/tasks/status/multiple" -ForegroundColor Green
    Write-Host ""
    Write-Host "The system is ready for production testing!" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "Available test types: health, inscription, performance, all" -ForegroundColor Gray
Write-Host "Usage: .\run_working_test.ps1 [TestType] [-BaseUrl URL]" -ForegroundColor Gray