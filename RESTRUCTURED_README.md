# TraStrainer - Restructured

This is a restructured version of the TraStrainer project, organized as a standard Python package with proper separation of concerns.

## Project Structure

```
src/trastrainer/                  # Main package directory
├── __init__.py                   # Package initialization and main exports
├── data_structures.py            # Data classes and type definitions
├── preprocessor.py               # Data preprocessing (metrics & traces)
├── algorithm.py                  # Main TraStrainer algorithm
├── predictors.py                 # Metric prediction functionality
├── utils.py                      # Utility functions
├── main.py                       # CLI entry point
├── legacy.py                     # Backward compatibility
└── models/                       # ML models for predictions
    ├── __init__.py
    └── linear_predictor.py        # Linear prediction models
```

## Key Improvements

### 1. **Structured Architecture**
- **Data Structures**: Clear definitions for `TraceData`, `MetricData`, `SamplingConfig`
- **Preprocessor**: Separated data loading and preprocessing logic
- **Algorithm**: Core TraStrainer sampling algorithm
- **Predictors**: Metric prediction functionality
- **Models**: ML model implementations

### 2. **Separation of Concerns**

#### Data Preprocessing (`preprocessor.py`)
- `MetricProcessor`: Handles metric data from CSV files
- `TraceProcessor`: Processes distributed trace data
- `DataPreprocessor`: Main preprocessing coordinator
- Support for both legacy and new data formats

#### Algorithm Implementation (`algorithm.py`)
- `SimilarityCalculator`: Computes trace structure similarity
- `FeatureExtractor`: Extracts features from trace data
- `SamplingFilter`: Implements system and diversity bias filters
- `SamplingDecision`: Makes sampling decisions
- `TraStrainerAlgorithm`: Main algorithm orchestrator

### 3. **Improved Data Structures**
```python
@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_id: str
    service_name: str
    operation_name: str
    start_time: str
    end_time: str
    duration: int
    status: str = "success"

@dataclass
class SamplingConfig:
    budget_sample_rate: float
    window_size: Optional[int] = None
    warm_up_size: int = 10
    checkpoints_dir: str = "./checkpoints"
```

### 4. **Better Logging**
- Standardized logging using `rcabench_platform.v2.logging`
- Proper log levels (INFO, DEBUG, WARNING, ERROR)
- Structured log messages

### 5. **Error Handling**
- Comprehensive exception handling
- Graceful fallbacks for missing models
- Input validation

## Usage

### New API (Recommended)
```python
from trastrainer import DataPreprocessor, TraStrainerAlgorithm, SamplingConfig

# Load data
preprocessor = DataPreprocessor()
traces, metrics = preprocessor.load_data("./data/test/")

# Configure algorithm
config = SamplingConfig(budget_sample_rate=0.1)
algorithm = TraStrainerAlgorithm(config)

# Run sampling
result = algorithm.run(traces, metrics)
print(f"Sampled {result.actual_sample_count} traces")
```

### Legacy API (Backward Compatible)
```python
from trastrainer import tra_strainer, process_metrics, read_traces

# Legacy usage (still works)
metrics = process_metrics("./data/test/")
traces = read_traces("./data/test/")
sampled_ids = tra_strainer(traces, metrics, 0.1)
```

### Command Line Interface
```bash
# Using the new CLI
python -m trastrainer.main --path ./data/test --rate 0.1

# Or using the legacy sampler
python sampler_new.py --path ./data/test --rate 0.1
```

## Algorithm Flow

### 1. **Data Preprocessing Phase**
```python
# Load traces and metrics from CSV files
traces, metrics = preprocessor.load_data(data_path)

# Extract system metrics from traces
system_metrics = preprocessor.extract_system_metrics(trace)

# Build trace trees for structure analysis
tree = TraceProcessor.build_trace_tree(trace.spans)
```

### 2. **Feature Extraction Phase**
```python
# Extract trace structure vector
structure = FeatureExtractor.get_trace_structure_vector(trace, tree)

# Compute feature values from system metrics
features = FeatureExtractor.compute_trace_feature_values(
    system_metrics, metrics
)
```

### 3. **Sampling Decision Phase**
```python
# Compute system bias sampling rate
system_rate = SamplingFilter.compute_system_bias_rate(
    history_metrics, trace_features, weights
)

# Compute diversity bias sampling rate  
diversity_rate = SamplingFilter.compute_diversity_bias_rate(
    history_structures, trace_structure, diversity_window
)

# Make final sampling decision
is_sample = SamplingDecision.judge(
    system_rate, diversity_rate, strict_mode
)
```

## Configuration Options

```python
config = SamplingConfig(
    budget_sample_rate=0.1,        # Target sampling rate (10%)
    window_size=10,                # History window size
    warm_up_size=10,               # Traces to process before sampling
    checkpoints_dir="./checkpoints" # Model checkpoint directory
)
```

## Data Formats Supported

### Trace Data
- **New Format**: Single CSV with columns: `TraceId`, `SpanId`, `ParentSpanId`, `ServiceName`, `SpanName`, `Timestamp`, `Duration`
- **Legacy Format**: Directory with multiple CSV files containing trace data

### Metric Data
- **New Format**: Single CSV with columns: `MetricName`, `ServiceName`, `TimeUnix`, `Value`, `ResourceAttributes`
- **Legacy Format**: Directory with metric CSV files containing time series data

## Extensions and Customization

The modular design allows easy extension:

```python
# Custom feature extractor
class CustomFeatureExtractor(FeatureExtractor):
    def get_custom_features(self, trace):
        # Custom feature extraction logic
        pass

# Custom sampling filter
class CustomSamplingFilter(SamplingFilter):
    def compute_custom_bias_rate(self, params):
        # Custom bias computation
        pass
```

## Testing

Run the example:
```python
from examples.basic_usage import run_trastrainer_example

result = run_trastrainer_example("./data/test/", 0.1)
```

## Migration from Original Code

1. **Import Changes**: 
   - Old: `from TraStrainer import tra_strainer`
   - New: `from trastrainer import tra_strainer` (still works)

2. **New Structured Approach**:
   - Use `DataPreprocessor` for data loading
   - Use `TraStrainerAlgorithm` for main logic
   - Use configuration objects for parameters

3. **Enhanced Results**:
   - Old: Returns list of trace IDs
   - New: Returns `SamplingResult` with detailed metrics

This restructured version maintains full backward compatibility while providing a much cleaner, more maintainable, and extensible architecture.
