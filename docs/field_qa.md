# Field QA — read these before the full abstraction run

**20 titles per field, hand-read.** Regenerate with `python3 data/sample_field_qa.py` (seeded from `corpus.yaml random_seed: 42`, so the sample is identical every time and is not cherry-picked).

## Why this exists

Field tags come from a deterministic OpenAlex subfield lookup, never an LLM. Home-field exclusion is `$nin` on `field`, so a wrong tag is not cosmetic:

- tagged **into** the user's home field -> a good cross-domain result is silently removed;
- tagged **out of** it -> a paper from their own field is returned as a "discovery".

That second one is the failure that makes the validation table meaningless, and it is invisible without a human reading titles. 160 reads is cheap insurance on 3,000 papers.

## How to mark it

For each line, mark **ok** if the paper reads as belonging in that field. Mark **wrong** if it plainly belongs elsewhere, and **borderline** if you would argue about it. Borderline lines are the useful ones: they are where the taxonomy is too coarse, and `corpus.yaml` already warns that subfield tagging is coarse.

**Target: under 5% wrong.** Above that, fix the subfield list in `config/corpus.yaml`, re-run `data/resolve_subfields.py`, and re-ingest. Do not hand-patch individual papers; the tag has to be reproducible.

---

## `robotics_mech_eng` — Robotics & Mechanical Engineering

20 of 375 shown. Subfields: Control and Systems Engineering, Mechanical Engineering

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 2009 | From PID to Active Disturbance Rejection Control |  |
| 2 | 2021 | Failure Pressure Prediction of a Corroded Pipeline with Longitudinally Interacting Corrosion Defects Subjected to Combined Loadings Using FEM and ANN |  |
| 3 | 1996 | Multivariable Feedback Control: Analysis and Design |  |
| 4 | 2025 | Enhancing Hydrophobicity of EPR ‐Based Rubber Compounds via Fumed Silica and Sulfur/Peroxide Curing Systems |  |
| 5 | 2016 | A critical review of high entropy alloys and related concepts |  |
| 6 | 2007 | Second Law Analysis of a non-Newtonian Laminar Falling Liquid Film Along an Inclined Heated Plate |  |
| 7 | 2006 | Overview of Control and Grid Synchronization for Distributed Power Generation Systems |  |
| 8 | 2018 | Investigations on the efficiency of truck axles and their hypoid gear set |  |
| 9 | 2014 | A fracture-resistant high-entropy alloy for cryogenic applications |  |
| 10 | 2015 | Design the Middleware of Intelligent Monitoring System for Vehicles |  |
| 11 | 1995 | Nonlinear and adaptive control design |  |
| 12 | 1996 | Some new generalizations of inertial manifolds |  |
| 13 | 1997 | Cellular solids structure and properties |  |
| 14 | 2019 | RANCANG BANGUN “AUTOMATIC TRANSFER SWITCH” DAN “AUTOMATIC MAINS FAILURE” (ATS DAN AMF) BERBASIS PLC DSE 4520 DENGAN TAMPILAN HUMAN MACHINE INTERFACE (HMI) |  |
| 15 | 1970 | Decision-Making in a Fuzzy Environment |  |
| 16 | 2016 | Design and Analysis Of Molybdenum Disulphide Coated Leaf Spring |  |
| 17 | 1989 | State-space solutions to standard H/sub 2/ and H/sub infinity / control problems |  |
| 18 | 2023 | Impact of power flow on the apparent impedance calculated by the distance protection in transmission lines |  |
| 19 | 2008 | ENSEMBLE EMPIRICAL MODE DECOMPOSITION: A NOISE-ASSISTED DATA ANALYSIS METHOD |  |
| 20 | 2011 | The synthesis of probability tests with a small number of kits |  |

**Tally for `robotics_mech_eng`:** ______ / 20 (wrong: ____  borderline: ____)

## `soft_matter_stat_physics` — Soft-Matter & Statistical Physics

20 of 375 shown. Subfields: Statistical and Nonlinear Physics, Condensed Matter Physics

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 1998 | Jamming, Force Chains, and Fragile Matter |  |
| 2 | 1977 | A Set of Measures of Centrality Based on Betweenness |  |
| 3 | 2025 | Symmetries and Closed-Form Solutions for Some Classes of Dynamical Systems |  |
| 4 | 1978 | Infinite-ranged models of spin-glasses |  |
| 5 | 1973 | Ordering, metastability and phase transitions in two-dimensional systems |  |
| 6 | 1976 | Some Remarks about Complexity |  |
| 7 | 2003 | Jamming at zero temperature and zero applied stress: The epitome of disorder |  |
| 8 | 2008 | Fast unfolding of communities in large networks |  |
| 9 | 2002 | The Form and Properties of the Tight-Binding Density of States in Two Dimensions. Possible Application to Superconductivity |  |
| 10 | 2001 | Jamming phase diagram for attractive particles |  |
| 11 | 1991 | Band theory and Mott insulators: Hubbard U instead of Stoner I |  |
| 12 | 2021 | Nambu dynamics and hydrodynamics of granular material |  |
| 13 | 1953 | Equation of State Calculations by Fast Computing Machines |  |
| 14 | 1962 | Optical Absorption Intensities of Rare-Earth Ions |  |
| 15 | 2012 | Thermodynamics of Information Processing in Small Systems*) |  |
| 16 | 1975 | Theory of spin glasses |  |
| 17 | 1987 | The Resonating Valence Bond State in La 2 CuO 4 and Superconductivity |  |
| 18 | 1987 | Specific heat of dilute Au-Fe and Cu-Mn spin-glass alloys below 30 K |  |
| 19 | 2004 | Finding and evaluating community structure in networks |  |
| 20 | 2012 | Analyses of dimensionless science |  |

**Tally for `soft_matter_stat_physics`:** ______ / 20 (wrong: ____  borderline: ____)

## `organismal_bio_ecology` — Organismal Biology & Ecology

20 of 375 shown. Subfields: Ecology, Evolution, Behavior and Systematics, Animal Science and Zoology

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 2002 | Evidence for van der Waals adhesion in gecko setae |  |
| 2 | 2009 | Fungal endophytes: diversity and functional roles |  |
| 3 | 2026 | Prevalence of Elephant Endotheliotropic Herpesvirus (EEHV) in Wild and Captive Bornean Elephants (Elephas maximus borneensis) Sampled During Conservation Management Activities in Sabah, Malaysia |  |
| 4 | 2006 | A mathematical model for adaptive transport network in path finding by true slime mold |  |
| 5 | 1990 | Behavioral decisions made under the risk of predation: a review and prospectus |  |
| 6 | 1988 | Morphological, Cytological, and Biochemical Differences Among Three Species of Nephotettix (Homoptera: Cicadellidae) in the Philippines |  |
| 7 | 2003 | From micro to nano contacts in biological attachment devices |  |
| 8 | 1990 | Modeling of the Bacterial Growth Curve |  |
| 9 | 2017 | Effects of dirty housing and a Salmonella Typhimurium DT104 challenge on pig growth performance, diet utilization efficiency, and gas emissions from stored manure1 |  |
| 10 | 2004 | Obtaining multiple separate food sources: behavioural intelligence in the Physarum plasmodium |  |
| 11 | 2016 | An update of the Angiosperm Phylogeny Group classification for the orders and families of flowering plants: APG IV |  |
| 12 | 2026 | Studies on Pygmy Grasshoppers: Bogotatettix Cadena‐Castañeda, García‐García & Tavares, gen. nov. (Orthoptera: Tetrigidae), a New Genus From the High Andean Forests and Páramos |  |
| 13 | 2000 | Adhesive force of a single gecko foot-hair |  |
| 14 | 2011 | How many flowering plants are pollinated by animals? |  |
| 15 | 2019 | Nutritional Intervention for the Intestinal Development and Health of Weaned Pigs |  |
| 16 | 2013 | Climate Change Impacts on Global Food Security |  |
| 17 | 2024 | Phylogenomic analysis of target enrichment and transcriptome data uncovers rapid radiation and extensive hybridization in the slipper orchid genus Cypripedium |  |
| 18 | 1976 | Life-History Tactics: A Review of the Ideas |  |
| 19 | 2013 | Evaluating the spectral discrimination capabilities of different pollinators and their effect on the evolution of flower colors |  |
| 20 | 1973 | Natural Selection of Parental Ability to Vary the Sex Ratio of Offspring |  |

**Tally for `organismal_bio_ecology`:** ______ / 20 (wrong: ____  borderline: ____)

## `medicine_clinical` — Medicine & Clinical Research

20 of 375 shown. Subfields: Internal Medicine, Surgery, Nephrology

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 1955 | THE DISTRIBUTION AND CHEMICAL COMPOSITION OF ULTRACENTRIFUGALLY SEPARATED LIPOPROTEINS IN HUMAN SERUM |  |
| 2 | 2008 | Conjugated Linoleic Acid Isomers Reduce Cholesterol Accumulation in Acetylated LDL‐Induced Mouse RAW264.7 Macrophage‐Derived Foam Cells |  |
| 3 | 2008 | Prediction of Creatinine Clearance from Serum Creatinine |  |
| 4 | 2008 | A multi-subject evaluation of uncertainty in anatomical landmark location on shoulder kinematic description |  |
| 5 | 2007 | Projections of Primary and Revision Hip and Knee Arthroplasty in the United States from 2005 to 2030 |  |
| 6 | 2005 | Hepatitis C Is a Predictor of Poorer Renal Survival in Diabetic Patients |  |
| 7 | 1979 | Glucose clamp technique: a method for quantifying insulin secretion and resistance. |  |
| 8 | 2003 | The investigation of the treatment of infection, complex defect of skin and bone in crus |  |
| 9 | 1995 | Prevention of Coronary Heart Disease with Pravastatin in Men with Hypercholesterolemia |  |
| 10 | 2026 | Spontaneous isolated celiac artery dissection: a rare mimicker of pancreatic mass masquerading as neoplasm |  |
| 11 | 2019 | 2019 ESC Guidelines for the diagnosis and management of chronic coronary syndromes |  |
| 12 | 2026 | Structured Feedback Tools in Surgical Training: Results of the Endo-Workshop of the German Society of Residents in Urology 2024 |  |
| 13 | 1976 | The Pharmacological Basis of Therapeutics |  |
| 14 | 2005 | Course of C‐reactive protein during continuous peritoneal dialysis‐associated peritonitis |  |
| 15 | 1993 | Summary of the second report of the National Cholesterol Education Program (NCEP) Expert Panel on Detection, Evaluation, and Treatment of High Blood Cholesterol in Adults (Adult Treatment Panel II) |  |
| 16 | 2021 | Loss of hepatic miR-33 improves metabolic homeostasis and liver function without altering body weight or atherosclerosis |  |
| 17 | 2012 | Classification of acute pancreatitis—2012: revision of the Atlanta classification and definitions by international consensus |  |
| 18 | 2014 | Effect of renal ischemia-reperfusion on lung injury and inflammatory responses in male rat. |  |
| 19 | 2012 | KDIGO Clinical Practice Guidelines for Acute Kidney Injury |  |
| 20 | 1999 | Apoptosis in pig leucocytes during cardiopulmonary bypass |  |

**Tally for `medicine_clinical`:** ______ / 20 (wrong: ____  borderline: ____)

## `economics_game_theory` — Economics & Game Theory

20 of 375 shown. Subfields: Economics and Econometrics

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 1984 | The Evolution of the Labor Market for Medical Interns and Residents: A Case Study in Game Theory |  |
| 2 | 1991 | Some Tests of Specification for Panel Data: Monte Carlo Evidence and an Application to Employment Equations |  |
| 3 | 2023 | Informality, Consumption Taxes, and Redistribution |  |
| 4 | 2003 | School Choice: A Mechanism Design Approach |  |
| 5 | 1985 | Economic Action and Social Structure: The Problem of Embeddedness |  |
| 6 | 2021 | Features of insurance risks’ classification as the basis of risk management of insurance companies in the financial crisis |  |
| 7 | 2008 | Estimating Standard Errors in Finance Panel Data Sets: Comparing Approaches |  |
| 8 | 2009 | The Role of Empirical Assumptions in Economic Analysis: On Facts and Counterfactuals in Economic Law |  |
| 9 | 1992 | A Contribution to the Empirics of Economic Growth |  |
| 10 | 2018 | Reorganization of Domestic Gas Market as a Factor of Russian Gas Companies' International Competitiveness |  |
| 11 | 2011 | Development and preliminary testing of the new five-level version of EQ-5D (EQ-5D-5L) |  |
| 12 | 2003 | Fading out" of the Actively Fiscal Policy:the Necessity,Condition and Strategies |  |
| 13 | 2016 | Measuring Economic Policy Uncertainty* |  |
| 14 | 2013 | Technological Progress and Employment:A Literature Review |  |
| 15 | 1986 | The Costs and Benefits of Ownership: A Theory of Vertical and Lateral Integration |  |
| 16 | 2024 | Effects of trade openness on environmental quality: evidence from developing countries |  |
| 17 | 1990 | Increasing Returns and Economic Geography |  |
| 18 | 1959 | Texas Attorney General Opinion: WW-569 |  |
| 19 | 1983 | An Evolutionary Theory of Economic Change. |  |
| 20 | 2012 | The Present Situation and Countermeasures of Real Estate Market in Liaoning Province |  |

**Tally for `economics_game_theory`:** ______ / 20 (wrong: ____  borderline: ____)

## `civil_transport_arch` — Civil, Transport & Architectural Engineering

20 of 375 shown. Subfields: Civil and Structural Engineering, Transportation, Building and Construction

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 2008 | BIM Handbook: A Guide to Building Information Modeling for Owners, Managers, Designers, Engineers and Contractors |  |
| 2 | 2019 | Cluster formation of ash and slag waters for production of building materials as a measure of environmental damage |  |
| 3 | 1979 | A discrete numerical model for granular assemblies |  |
| 4 | 2024 | Integrating Occupant Behaviour into Urban-Building Energy Modelling: A Review of Current Practices and Challenges |  |
| 5 | 1998 | A Summary Review of Vibration-Based Damage Identification Methods |  |
| 6 | 2004 | Relationship between temperature sensitivity of capillary pressure and soil particle size |  |
| 7 | 1988 | Theoretical Stress‐Strain Model for Confined Concrete |  |
| 8 | 2015 | Optimizing Small Hydropower Systems in Water Distribution Systems Based on Long-Time-Series Simulation and Future Scenarios |  |
| 9 | 2017 | Deep Learning‐Based Crack Damage Detection Using Convolutional Neural Networks |  |
| 10 | 2017 | Assessment of seismic design provisions for multi-tiered ordinary concentrically braced frames |  |
| 11 | 2003 | A Framework to Quantitatively Assess and Enhance the Seismic Resilience of Communities |  |
| 12 | 2013 | Analysis of Skew Deck Slab Bridge by Analytical Methods |  |
| 13 | 1976 | A new model for predicting the hydraulic conductivity of unsaturated porous media |  |
| 14 | 1983 | Behaviour and design of stiffened plates under predominantly compressive loads1 |  |
| 15 | 1959 | How Accessibility Shapes Land Use |  |
| 16 | 2014 | MAP-21, GIS, the Road Inventory and YOU |  |
| 17 | 2010 | Limits of Predictability in Human Mobility |  |
| 18 | 2014 | Seismic Performance of Multistorey Building with Soft Storey at Different Level with RC Shear Wall |  |
| 19 | 1994 | Equations for the soil-water characteristic curve |  |
| 20 | 2014 | Banana Aqueous Extract as a Potential Addition to Clay Ceramics |  |

**Tally for `civil_transport_arch`:** ______ / 20 (wrong: ____  borderline: ____)

## `cs_optimization` — Computer Science & Optimization

20 of 375 shown. Subfields: Artificial Intelligence, Computer Networks and Communications, Management Science and Operations Research, Computational Theory and Mathematics

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 2020 | SciPy 1.0: fundamental algorithms for scientific computing in Python |  |
| 2 | 2015 | Evaluation of the Psychometric Properties of the Asian Adolescent Depression Scale and Construction of a Short Form: An Item Response Theory Analysis |  |
| 3 | 1977 | Maximum Likelihood from Incomplete Data Via the EM Algorithm |  |
| 4 | 1995 | Discovering Complex Othello Strategies through Evolutionary Neural Networks |  |
| 5 | 1951 | Coefficient Alpha and the Internal Structure of Tests |  |
| 6 | 1999 | Auctions without Common Knowledge |  |
| 7 | 2002 | SMOTE: Synthetic Minority Over-sampling Technique |  |
| 8 | 1997 | A Survey of Neural Network Publications. |  |
| 9 | 2002 | A fast and elitist multiobjective genetic algorithm: NSGA-II |  |
| 10 | 2014 | Homogenization of fluid–porous interface coupling in a biconnected fractured media |  |
| 11 | 2014 | A new criterion for assessing discriminant validity in variance-based structural equation modeling |  |
| 12 | 2006 | CONVEX GRID DRAWINGS OF FOUR-CONNECTED PLANE GRAPHS |  |
| 13 | 1948 | A Mathematical Theory of Communication |  |
| 14 | 1999 | A static analysis for classical linear logic programming language |  |
| 15 | 1977 | The CES-D Scale |  |
| 16 | 2021 | Waveform Level Intelligent Multi-Task Receiver With BiLSTM |  |
| 17 | 1983 | A Global Measure of Perceived Stress |  |
| 18 | 2013 | ANALYSIS OF DYNAMIC SOURCE ROUTING IN WIRELESS AD-HOC NETWORKS |  |
| 19 | 2026 | AutoResearch Lite: a reproducible paper-inspired experiment runner (Adam mechanism reproduction and convergence-speed comparison) |  |
| 20 | 2018 | Binary States Cellular Automata with Reflexive and Periodic Boundaries and Image problem |  |

**Tally for `cs_optimization`:** ______ / 20 (wrong: ____  borderline: ____)

## `materials_fluids_aero` — Materials, Fluids & Aerospace Engineering

20 of 375 shown. Subfields: Aerospace Engineering, Mechanics of Materials, Surfaces, Coatings and Films, Fluid Flow and Transfer Processes

| # | year | title | looks right? |
|---|---|---|---|
| 1 | 1979 | Quantitative electron spectroscopy of surfaces: A standard data base for electron inelastic mean free paths in solids |  |
| 2 | 2020 | EFFECT OF RADIATION HEATING OF CONSTRUCTION MATERIALS OF AN EXPERIMENTAL DEVICE WITH A NEUTRON CONVERTER ON THEIR TEMPERATURE REGIME |  |
| 3 | 1936 | RESISTANCE OF SOLID SURFACES TO WETTING BY WATER |  |
| 4 | 2022 | Micro-Motion Parameter Extraction of Multi-Scattering-Point Target Based on Vortex Electromagnetic Wave Radar |  |
| 5 | 1953 | Contact and Rubbing of Flat Surfaces |  |
| 6 | 2021 | Offline and Online UAV-Enabled Data Collection in Time-Constrained IoT Networks |  |
| 7 | 1994 | Element‐free Galerkin methods |  |
| 8 | 2014 | Optimization Approach to Design Single Feed Symmetric and Asymmetric Multibeam Reflectarrays |  |
| 9 | 1997 | Fuzzy Nanoassemblies: Toward Layered Polymeric Multicomposites |  |
| 10 | 2022 | Atmospheric Ducting Interference on DAB, DAB+ Radio in Eastern Mediterranean |  |
| 11 | 2017 | ORB-SLAM2: An Open-Source SLAM System for Monocular, Stereo, and RGB-D Cameras |  |
| 12 | 2012 | Westinghouse Small Modular Reactor passive safety system response to postulated events |  |
| 13 | 1972 | High-Resolution X-Ray Photoemission Spectrum of the Valence Bands of Gold |  |
| 14 | 1985 | Viscosities and activation energies of viscous flow of the ternary mixtures of n-hexane, toluene, chlorobenzene, and 1-hexanol |  |
| 15 | 2001 | Permanent scatterers in SAR interferometry |  |
| 16 | 2023 | Critical velocities of a two-layer composite tube incorporating the effects of transverse shear, rotary inertia and material anisotropy |  |
| 17 | 1982 | Antenna Theory: Analysis and Design |  |
| 18 | 1997 | Activation of coagulation and platelets is affected by the hydrophobicity of artificial surfaces |  |
| 19 | 1981 | A Critical Evaluation of Indentation Techniques for Measuring Fracture Toughness: I, Direct Crack Measurements |  |
| 20 | 2003 | SYNTHETIC STUDIES ON BLOOD COMPATIBLE BIOMATERIALS13: A NOVEL SEGMENTED POLYURETHANE CONTAINING PHOSPHORYLCHOLINE STRUCTURE:SYNTHESIS,CHARACTERIZATION AND BLOOD COMPATIBILITY EVALUATION |  |

**Tally for `materials_fluids_aero`:** ______ / 20 (wrong: ____  borderline: ____)

---

## Verdict

| field | shown | wrong | borderline | verdict |
|---|---|---|---|---|
| `robotics_mech_eng` | 20 | | | |
| `soft_matter_stat_physics` | 20 | | | |
| `organismal_bio_ecology` | 20 | | | |
| `medicine_clinical` | 20 | | | |
| `economics_game_theory` | 20 | | | |
| `civil_transport_arch` | 20 | | | |
| `cs_optimization` | 20 | | | |
| `materials_fluids_aero` | 20 | | | |

If any field is over 5% wrong, **stop and fix the subfield mapping** before running the abstraction batch. Re-abstracting 3,000 papers with a wrong tag costs the pilot, and the pilot exists precisely to catch this.
