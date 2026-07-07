import argparse
import ROOT
from podio import root_io


def make_hist_file(args):
    print(f'INFO: Input EDM4hep file: {args.inputFile}')
    print(f'INFO: Output histogram file: {args.outputFile}')

    # create output ROOT file
    outputFile = ROOT.TFile(args.outputFile, "RECREATE")

    # set file reader
    podio_reader = root_io.Reader(args.inputFile)

    # set list of directories in ROOT file (one per subsystem to check)
    dir_list = []
    # set list of (list of) histograms created (one list per subsystem to check)
    histo_list = []

    dir_ECalBarrel = outputFile.mkdir("ECalBarrel")

    hist_ccE = ROOT.TH1F(
        "h_CaloCluster_E",
        "CaloCluster Energy;Energy [MeV];Counts / 0.15 MeV",
        100,
        0,
        15,
    )
    hist_ctcE = ROOT.TH1F(
        "h_CaloTopoCluster_E",
        "CaloTopoCluster Energy;Energy [MeV];Counts / 0.15 MeV",
        100,
        0,
        15,
    )
    hist_ecal_totE = ROOT.TH1F(
        "h_ECalBarrelModuleThetaMergedPositioned_totE",
        "ECalBarrelModuleThetaMergedPositioned total Energy per evt;Energy [MeV];"
        "Counts / 0.15 MeV",
        100,
        0,
        15,
    )
    hist_ecal_posX = ROOT.TH1F(
        "h_ECalBarrelModuleThetaMergedPositioned_posX",
        "ECalBarrelModuleThetaMergedPositioned position X;X [mm];Counts / 37 mm",
        150,
        -2770,
        2770,
    )
    hist_ecal_posY = ROOT.TH1F(
        "h_ECalBarrelModuleThetaMergedPositioned_posY",
        "ECalBarrelModuleThetaMergedPositioned position Y;Y [mm];Counts / 37 mm",
        150,
        -2770,
        2770,
    )
    hist_ecal_posZ = ROOT.TH1F(
        "h_ECalBarrelModuleThetaMergedPositioned_posZ",
        "ECalBarrelModuleThetaMergedPositioned position Z;Z [mm];Counts / 41 mm",
        150,
        -3100,
        3100,
    )

    dir_list.append(dir_ECalBarrel)
    histo_list.append(
        [
            hist_ccE,
            hist_ctcE,
            hist_ecal_totE,
            hist_ecal_posX,
            hist_ecal_posY,
            hist_ecal_posZ,
        ]
    )

    # Loop over dataset
    for event in podio_reader.get("events"):

        for calo in event.get("CaloClusterCells"):
            hist_ccE.Fill(calo.getEnergy())

        for calo in event.get("CaloTopoClusterCells"):
            hist_ctcE.Fill(calo.getEnergy())

        energy = 0
        for ecal in event.get("ECalBarrelModuleThetaMergedPositioned"):
            energy += ecal.getEnergy()
            hist_ecal_posX.Fill(ecal.getPosition().x)
            hist_ecal_posY.Fill(ecal.getPosition().y)
            hist_ecal_posZ.Fill(ecal.getPosition().z)
        hist_ecal_totE.Fill(energy)

    # normalize if desired
    if args.norm:
        n_evts = len(podio_reader.get("events"))
        factor = 1.0 / n_evts
        for l in histo_list:
            for h in l:
                h.Scale(factor)

    # save to file
    for dir, h_list in zip(dir_list, histo_list):
        dir.cd()
        for h in h_list:
            h.Write()

    outputFile.Close()


# #############################################################################
def main():
    '''
    Parse input arguments and start generation of the histograms.
    '''
    parser = argparse.ArgumentParser(description="Process simulation")
    parser.add_argument(
        "-f",
        "--inputFile",
        type=str,
        help="The name of the simulation file to be processed",
        default="ALLEGRO_sim_digi_reco.root",
    )
    parser.add_argument(
        "-o",
        "--outputFile",
        type=str,
        help="The name of the ROOT file where to save output histograms",
        default="results.root",
    )
    parser.add_argument(
        "--norm",
        action="store_true",
        help="Normalize output histograms by number of events",
    )
    args = parser.parse_args()

    make_hist_file(args)


if __name__ == "__main__":
    main()
